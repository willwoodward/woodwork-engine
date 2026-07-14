import asyncio
import logging
import threading
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from woodwork.components.llms.llm import LLM
from woodwork.components.streaming_mixin import StreamingMixin
from woodwork.utils import format_kwargs, get_optional

log = logging.getLogger(__name__)


class OpenAILLM(LLM):
    def __init__(self, api_key: str, model="gpt-4o-mini", **config):
        format_kwargs(config, api_key=api_key, model=model, type="openai")
        log.debug("Establishing connection with OpenAI model...")
        self._model = model
        self._api_key = api_key
        self._llm_value = None
        self._retriever = get_optional(config, "knowledge_base")
        if self._retriever is not None:
            self._retriever = self._retriever.retriever

        if self._model == "gpt-5-mini":
            self._llm_value = ChatOpenAI(
                model=self._model,
                max_tokens=None,
                timeout=None,
                max_retries=2,
                api_key=self._api_key,
                streaming=False,
            )

        super().__init__(**config)

    @property
    def _llm(self):
        return self._llm_value

    @property
    def retriever(self):
        return self._retriever

    def initialize(self) -> None:
        """Initialise the LLM client (called before start)."""
        if self._model == "gpt-5-mini":
            log.debug("OpenAI model already initialised.")
            return
        self._llm_value = ChatOpenAI(
            model=self._model,
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            api_key=self._api_key,
            streaming=True,
        )
        log.debug("OpenAI model initialized.")

    # Keep legacy start() for backwards-compat with old runtime paths
    def start(self, queue=None, config=None):
        self.initialize()
        import time
        time.sleep(1)

    def parallel_start(self, queue=None, config=None):
        import time
        time.sleep(1)

    async def _generate_and_stream_output(self, input_data: Any, stream_id: str):
        def _sync_streaming():
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)

                async def _async_stream():
                    prompt = str(input_data)
                    short_term_memory = self._get_short_term_memory()

                    if self._memory:
                        system_prompt = (
                            "You are a helpful assistant, answer the provided question, In 3 sentences or less. {memory}"
                        ).format(memory=short_term_memory)
                    else:
                        system_prompt = (
                            "You are a helpful assistant, answer the provided question, In 3 sentences or less."
                        )

                    chat_prompt = ChatPromptTemplate.from_messages(
                        [("system", system_prompt), ("human", "{input}")]
                    )
                    chain = chat_prompt | self._llm

                    async for chunk in chain.astream({"input": prompt}):
                        if hasattr(chunk, "content") and chunk.content:
                            asyncio.run_coroutine_threadsafe(
                                self.stream_output(stream_id, chunk.content, is_final=False),
                                self._original_loop,
                            ).result()

                    asyncio.run_coroutine_threadsafe(
                        self.stream_output(stream_id, "", is_final=True), self._original_loop
                    ).result()

                    if self._memory:
                        self._memory.add(f"[USER] {prompt}")
                        self._memory.add("[AI] <streamed response>")

                new_loop.run_until_complete(_async_stream())
            except Exception as exc:
                log.error("OpenAI LLM streaming error: %s", exc)
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.stream_output(stream_id, f"Error: {exc}", is_final=True),
                        self._original_loop,
                    ).result()
                except Exception:
                    pass
            finally:
                new_loop.close()

        try:
            self._original_loop = asyncio.get_running_loop()
            thread = threading.Thread(target=_sync_streaming)
            thread.start()
        except Exception as exc:
            log.error("OpenAI LLM streaming setup error: %s", exc)
            await self.stream_output(stream_id, f"Error: {exc}", is_final=True)
