"""Abstract LLM base class."""

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from woodwork.components.component import Component
from woodwork.components.streaming_mixin import StreamingMixin
from woodwork.interfaces.tool_interface import tool_interface
from woodwork.interfaces.knowledge_base_interface import knowledge_base_interface
from woodwork.types import Prompt
from woodwork.utils import format_kwargs, get_prompt

import logging

log = logging.getLogger(__name__)


class LLM(Component, StreamingMixin, tool_interface, knowledge_base_interface, ABC):
    def __init__(self, **config):
        format_kwargs(config, component="llm")
        super().__init__(**config)

        self._prompt_config = Prompt.from_dict(config.get("prompt", {"file": "prompts/defaults/llm.txt"}))
        self._prompt = get_prompt(self._prompt_config.file)
        self._memory = config.get("memory")
        self._output = config.get("to")

    def _can_stream_input(self) -> bool:
        return False

    def _can_stream_output(self) -> bool:
        return True

    @property
    @abstractmethod
    def _llm(self):
        pass

    # ------------------------------------------------------------------ #
    # New clean call() API — used by AgentLoop                           #
    # ------------------------------------------------------------------ #

    async def call(self, system_prompt: str, history: str, query: str) -> str:
        """
        Call the LLM with a system prompt and user query.

        Returns the response content as a plain string.
        """
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )
        chain = prompt | self._llm
        response = chain.invoke({"input": query})
        try:
            return response.content
        except AttributeError:
            return str(response)

    # ------------------------------------------------------------------ #
    # Legacy tool_interface / knowledge_base_interface methods           #
    # ------------------------------------------------------------------ #

    def _get_short_term_memory(self):
        if self._memory:
            return f"Here are the previous messages as context: \n{self._memory.data}"
        return ""

    def question_answer(self, query, short_term_memory=""):
        if self._memory:
            system_prompt = (
                "You are a helpful assistant, answer the provided question, In 3 sentences or less. {memory}"
            ).format(memory=short_term_memory)
        else:
            system_prompt = "You are a helpful assistant, answer the provided question, In 3 sentences or less. "

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )
        chain = prompt | self._llm
        response = chain.invoke({"input": query})
        try:
            return response.content
        except AttributeError:
            return response

    def context_answer(self, query, short_term_memory=""):
        results = self._retriever.invoke(query)
        context_parts = []
        for x in results:
            content = x.page_content.replace("{", "{{").replace("}", "}}")
            file_path = x.metadata.get("file_path", "unknown file")
            context_parts.append(f"[File: {file_path}]\n{content}")
        context = "\n\n".join(context_parts)

        system_prompt = (
            "Use the given context to answer the question. "
            "If you don't know the answer, say you don't know. "
            "Mention the relevant file names within a single, concise sentence or brief paragraph. "
            "Do not list files or describe each file separately. "
            "Instead, provide a smooth, natural summary that integrates the file names and their roles. "
            "Return only the answer to the question. "
            "Context: {context}"
            "{memory}"
        ).format(context=context, memory=short_term_memory)

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )
        chain = prompt | self._llm
        response = chain.invoke({"input": query})
        try:
            return response.content
        except AttributeError:
            return response

    @property
    def description(self):
        return """Ask the LLM a prompt in the form of the string and it will return an answer to that prompt.
            The action is the prompt, and inputs represent a dictionary where keys in the prompt will be substituted in for their value.
            The input value should reference a string or variable name from one of the previous action's output.
            Contain the LLM prompt inside action, with curly braces to denote variable inputs, and then containing the variable inputs inside the inputs dictionary.
            The LLM will automatically use a knowledge base if one is attached for RAG.
            """

    def input(self, query: str, inputs: dict = {}) -> str | None:
        prompt = query
        for key in inputs:
            prompt = prompt.replace(f"{{{key}}}", str(inputs[key]))

        short_term_memory = self._get_short_term_memory()
        if self._retriever is None:
            answer = self.question_answer(prompt, short_term_memory)
        else:
            answer = self.context_answer(prompt, short_term_memory)

        if self._memory:
            self._memory.add(f"[USER] {query}")
            self._memory.add(f"[AI] {answer}")

        return answer

    async def execute(self, action: str, inputs: dict = {}) -> str | None:
        """New execute() alias for tool_interface compatibility."""
        return self.input(action, inputs)

    async def process(self, query: str) -> str:
        log.debug("LLM processing query: '%s', streaming_output=%s", query, self.streaming_output)
        if self.streaming_output:
            result = await self.process_with_streaming_output(query)
            return result
        return self.input(query)

    async def _generate_and_stream_output(self, input_data: Any, stream_id: str):
        try:
            response = self.input(str(input_data))
            await self.stream_output(stream_id, response, is_final=True)
        except Exception as exc:
            log.error("LLM streaming error: %s", exc)
            await self.stream_output(stream_id, f"Error: {exc}", is_final=True)
