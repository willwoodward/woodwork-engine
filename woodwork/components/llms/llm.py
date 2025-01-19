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

    @property
    @abstractmethod
    def _llm(self):
        pass

    def question_answer(self, query):
        # Defining the system prompt
        if self._memory:
            system_prompt = (
                "You are a helpful assistant, answer the provided question, "
                "In 3 sentences or less. "
                "Here are the previous messages as context: "
                "{context}"
            ).format(context=self._memory.data)
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

        # Adding to memory
        if self._memory:
            self._memory.add(f"[USER] {query}")
            self._memory.add(f"[AI] {response}")

        return response

    def context_answer(self, query):
        results = self._retriever.invoke(query)

        system_prompt = (
            "Use the given context to answer the question. "
            "If you don't know the answer, say you don't know. "
            "Use three sentence maximum and keep the answer concise. "
            "Return only the answer to the question. "
            "Context: {context}"
        ).format(context="\n".join(list(map(lambda x: x.page_content, results))))

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

    def input(self, query: str, inputs: dict = {}) -> str:
        # Substitute inputs
        prompt = query
        for key in inputs:
            prompt = prompt.replace(f"{{{key}}}", str(inputs[key]))

        # If there is no retriever object, there is no connected Knowledge Base
        if self._retriever is None:
            return self.question_answer(prompt)
        else:
            return self.context_answer(prompt)
