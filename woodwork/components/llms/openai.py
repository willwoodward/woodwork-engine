import logging
import multiprocessing
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import time
from typing import Any

from woodwork.components.llms.llm import llm
from woodwork.interfaces import ParallelStartable, Startable
from woodwork.utils import format_kwargs, get_optional

log = logging.getLogger(__name__)


class openai(llm, ParallelStartable, Startable):
    def __init__(self, api_key: str, model="gpt-4o-mini", **config):
        format_kwargs(config, api_key=api_key, model=model, type="openai")
        log.debug("Establishing connection with model...")
        self._model = model
        self._api_key = api_key
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
                streaming=False,  # Enable streaming support
            )

        super().__init__(**config)

    @property
    def _llm(self):
        return self._llm_value

    @property
    def retriever(self):
        return self._retriever

    def parallel_start(self, queue: multiprocessing.Queue, config: dict = {}):
        time.sleep(1)

    def start(self, queue: multiprocessing.Queue, config: dict = {}):
        if self._model == "gpt-5-mini":
            log.debug("Model initialized.")
            return
        self._llm_value = ChatOpenAI(
            model=self._model,
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            api_key=self._api_key,
            streaming=True,  # Enable streaming support
        )
        time.sleep(1)
        log.debug("Model initialized.")

    async def _generate_and_stream_output(self, input_data: Any, stream_id: str):
        """Generate streaming response using OpenAI's streaming API"""
        def _sync_streaming():
            """Run streaming in a separate thread with its own event loop"""
            try:
                # Create a new event loop for this thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                
                async def _async_stream():
                    log.debug(f"OpenAI LLM generating streaming output for stream {stream_id}, input: '{input_data}'")
                    
                    # Prepare the prompt using the same logic as the base class
                    prompt = str(input_data)
                    short_term_memory = self._get_short_term_memory()
                    
                    # Use question_answer logic but with streaming
                    if self._memory:
                        system_prompt = (
                            "You are a helpful assistant, answer the provided question, In 3 sentences or less. {memory}"
                        ).format(memory=short_term_memory)
                    else:
                        system_prompt = "You are a helpful assistant, answer the provided question, In 3 sentences or less."
                    
                    chat_prompt = ChatPromptTemplate.from_messages([
                        ("system", system_prompt),
                        ("human", "{input}"),
                    ])
                    
                    # Create streaming chain
                    chain = chat_prompt | self._llm
                    
                    # Stream the response
                    async for chunk in chain.astream({"input": prompt}):
                        if hasattr(chunk, 'content') and chunk.content:
                            # We need to call stream_output in the original event loop
                            asyncio.run_coroutine_threadsafe(
                                self.stream_output(stream_id, chunk.content, is_final=False),
                                self._original_loop
                            ).result()
                    
                    # Mark as final
                    asyncio.run_coroutine_threadsafe(
                        self.stream_output(stream_id, "", is_final=True),
                        self._original_loop
                    ).result()
                    
                    # Add to memory after completion
                    if self._memory:
                        self._memory.add(f"[USER] {prompt}")
                        self._memory.add(f"[AI] <streamed response>")
                    
                    log.debug(f"OpenAI LLM finished streaming for stream {stream_id}")
                
                # Run the async streaming
                new_loop.run_until_complete(_async_stream())
                
            except Exception as e:
                log.error(f"OpenAI LLM streaming error: {e}")
                try:
                    # Send error back to original loop
                    asyncio.run_coroutine_threadsafe(
                        self.stream_output(stream_id, f"Error: {e}", is_final=True),
                        self._original_loop
                    ).result()
                except:
                    log.error(f"Failed to send error message to stream {stream_id}")
            finally:
                new_loop.close()
        
        try:
            # Store the original event loop
            self._original_loop = asyncio.get_running_loop()
            
            # Run streaming in a separate thread to avoid executor shutdown issues
            thread = threading.Thread(target=_sync_streaming)
            thread.start()
            
        except Exception as e:
            log.error(f"OpenAI LLM streaming setup error: {e}")
            try:
                await self.stream_output(stream_id, f"Error: {e}", is_final=True)
            except:
                log.error(f"Failed to send error message to stream {stream_id}")
