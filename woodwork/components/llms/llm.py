from woodwork.components.component import component
from woodwork.interfaces.tool_interface import tool_interface
from woodwork.interfaces.knowledge_base_interface import knowledge_base_interface
from woodwork.helper_functions import format_kwargs

from langchain_core.prompts import ChatPromptTemplate
from abc import ABC, abstractmethod


class llm(component, tool_interface, knowledge_base_interface, ABC):
    def __init__(self, **config):
        format_kwargs(config, component="llm")
        super().__init__(**config)

        self._memory = config.get("memory")
        self._output = config.get("to")

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
        context = "\n".join([x.page_content.replace("{", "{{").replace("}", "}}") for x in results])

        system_prompt = (
            "Use the given context to answer the question. "
            "If you don't know the answer, say you don't know. "
            "Use three sentence maximum and keep the answer concise. "
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
