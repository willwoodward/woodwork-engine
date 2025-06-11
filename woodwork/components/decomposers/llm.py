import json
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from typing import Any

from woodwork.components.decomposers.decomposer import decomposer
from woodwork.helper_functions import format_kwargs

log = logging.getLogger(__name__)


class llm(decomposer):
    def __init__(self, api_key: str, **config):
        format_kwargs(config, api_key=api_key, type="llm")
        super().__init__(**config)
        log.debug("Initializing decomposer...")

        self.__llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            api_key=api_key,
        )

        # self.__retriever = None
        # if "knowledge_base" in config:
        #     self.__retriever = config["knowledge_base"].retriever

    def __clean(self, x):
        start_index = -1
        end_index = -1

        for i in range(len(x) - 1):
            if x[i] == "{":
                start_index = i
                break

        for i in range(len(x) - 1, 0, -1):
            if x[i] == "}":
                end_index = i
                break

        if start_index == -1:
            return x

        try:
            return json.loads(x[start_index : end_index + 1 :])
        except:
            log.debug("Couldn't load array as JSON")
            log.debug(x[start_index : end_index + 1 :])
            return x

    def _find_inputs(self, query: str, inputs: list[str]) -> dict[str, Any]:
        """Given a prompt and the inputs to be extracted, return the input dictionary."""
        system_prompt = (
            "Given the following prompt from the user, and a list of inputs:"
            "{inputs} \n"
            "Extract these from the user's prompt, and return in the following JSON schema:"
            "{{{{input: extracted_text}}}}\n"
            "For example, if the user's prompt is: what are the letters in the word chicken?, given the inputs: ['word']"
            'The output would be: {{{{"word": "chicken"}}}}\n'
            "When including data structures other than strings for the value, do not wrap them in a string."
            "Return only this JSON object."
        ).format(inputs=inputs)

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )

        chain = prompt | self.__llm
        result = chain.invoke({"input": query}).content

        # Clean output as JSON
        result = self.__clean(result)
        return result

    def _generate_workflow(self, query: str, partial_workflow: dict[str, Any]):
        input_dict = self._find_inputs(query, partial_workflow["inputs"])
        workflow = {"inputs": input_dict, "plan": partial_workflow["actions"]}
        return workflow

    def input(self, query):
        # Search cache for similar results
        if self._cache_mode:
            closest_query = self._cache_search_actions(query)
            if closest_query["score"] > 0.90:
                log.debug("Cache hit!")
                return self._output.execute(self._generate_workflow(query, closest_query))

        tool_documentation = ""
        for obj in self._tools:
            tool_documentation += f"tool name: {obj.name}\ntool type: {obj.type}\n{obj.description}\n\n\n"

        log.debug(f"[DOCUMENTATION]:\n{tool_documentation}")
        system_prompt = (
            "Given the following tools and their descriptions:\n"
            "{tools} "
            "Answer the user's prompt, returning only the necessary action plan "
            "to carry out the steps to solving the user's prompt. "
            "If you do not have necessary tools, say so."
            "Structure your steps in the following schema: "
            '[{{{{"tool": tool, "action": prompt, function or endpoint, "inputs": {{{{variable: value}}}}, "output": value}}}}, ...]'
            "Format this JSON into an array of steps, returing only this array. "
            "Include only these keys in the JSON object, no others. "
            "Specify only the function or endpoint name as an action when they are used, do not include them as a function key. "
            "If you do not have the necessary information, ask for the required information. "
            "Always specify an output variable. "
            "Once this array of steps has been constructed, insert it into the following JSON schema: "
            '{{{{"name": name, "inputs": dictionary of inputs, "plan": array of steps}}}}'
            "The name should be the user's prompt, with input variables in curly braces and proper punctuation."
            "The dictionary of inputs should have keys as the input variables, and values as the hardcoded value to be substituted into the name. These will be replaced whenever the action is called."
            "For example, a prompt could be: what is the length of the word orange, which will have name: What is the length of the word {{{{word}}}}?"
            'Where the dictionary of inputs is {{{{"word": "orange"}}}}.'
            "The inputs of the action plan should not be hardcoded. Using this example:"
            '{{{{"inputs": {{{{"word": "word"}}}}}}}}, not {{{{"inputs": {{{{"word": "orange"}}}}}}}}.'
            "Just a reminder that inputs of the plan should be a string (which references a variable), and not wrapped in curly braces when used as a key."
            "And an extra reminder that the inputs inside an action plan should not be hardcoded. For example, if the word changed, the action plan should be able to execute on the different word."
            "Return only this fully constructed JSON object."
        ).format(tools=tool_documentation)

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )

        chain = prompt | self.__llm
        result = chain.invoke({"input": query}).content

        log.debug(f"[RESULT] {result}")

        # Clean output as JSON
        result = self.__clean(result)

        log.debug(f"[RESULT] {result}")

        if isinstance(result, str):
            return result

        # Cache instructions
        if self._cache_mode:
            self._cache_actions(result)

        # Send to task_master
        return self._output.execute(result)
