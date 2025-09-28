from woodwork.components.component import component
from woodwork.interfaces.tool_interface import tool_interface
from woodwork.interfaces.knowledge_base_interface import knowledge_base_interface
from woodwork.types import Prompt
from woodwork.utils import format_kwargs, get_prompt

from langchain_core.prompts import ChatPromptTemplate
from abc import ABC, abstractmethod
import asyncio
from typing import Any
import logging

log = logging.getLogger(__name__)


class llm(component, tool_interface, knowledge_base_interface, ABC):
    def __init__(self, **config):
        format_kwargs(config, component="llm")
        super().__init__(**config)

        self._prompt_config = Prompt.from_dict(config.get("prompt", {"file": "prompts/defaults/llm.txt"}))
        self._prompt = get_prompt(self._prompt_config.file)
        self._memory = config.get("memory")
        self._output = config.get("to")
    
    def _can_stream_input(self) -> bool:
        """LLMs cannot stream input - they need the complete prompt"""
        return False
    
    def _can_stream_output(self) -> bool:
        """LLMs can stream output when supported"""
        return True

    @property
    @abstractmethod
    def _llm(self):
        pass

    def _get_short_term_memory(self):
        if self._memory:
            return f"Here are the previous messages as context: \n{self._memory.data}"
        return ""

    def question_answer(self, query, short_term_memory=""):
        # Defining the system prompt
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
            response = response.content
        except:
            pass
        return response

    def context_answer(self, query, short_term_memory=""):
        results = self._retriever.invoke(query)

        context_parts = []
        for x in results:
            # Escape braces in content for formatting safety
            content = x.page_content.replace("{", "{{").replace("}", "}}")
            # Extract the file_path metadata (change key if yours is different)
            file_path = x.metadata.get("file_path", "unknown file")

            # Format how you want the metadata to appear — here just prefixing
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
            response = response.content
        except:
            pass

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
        # Substitute inputs
        prompt = query
        for key in inputs:
            prompt = prompt.replace(f"{{{key}}}", str(inputs[key]))

        short_term_memory = self._get_short_term_memory()
        answer = ""
        if self._retriever is None:
            answer = self.question_answer(prompt, short_term_memory)
        else:
            answer = self.context_answer(prompt, short_term_memory)

        # Adding to short-term memory
        if self._memory:
            self._memory.add(f"[USER] {query}")
            self._memory.add(f"[AI] {answer}")

        return answer
    
    
    async def process(self, query: str) -> str:
        """Process input with optional streaming output"""
        log.debug(f"LLM processing query: '{query}', streaming_output={self.streaming_output}")
        if self.streaming_output:
            result = await self.process_with_streaming_output(query)
            log.debug(f"LLM streaming result: {result}")
            return result
        else:
            result = self.input(query)
            log.debug(f"LLM non-streaming result: {result}")
            return result
    
    async def _generate_and_stream_output(self, input_data: Any, stream_id: str):
        """Generate and stream LLM response - override in subclasses"""
        try:
            log.debug(f"LLM generating streaming output for stream {stream_id}, input: '{input_data}'")
            
            # Default implementation: get full response and send as single chunk
            # Subclasses should override this for proper streaming
            response = self.input(str(input_data))
            await self.stream_output(stream_id, response, is_final=True)
                
        except Exception as e:
            log.error(f"LLM streaming error: {e}")
            await self.stream_output(stream_id, f"Error: {e}", is_final=True)
