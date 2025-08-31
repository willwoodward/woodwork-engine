import json
import re
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from typing import Any, Tuple, Optional

from woodwork.components.agents.agent import agent
from woodwork.utils import format_kwargs, get_optional, get_prompt
from woodwork.types import Action, Prompt

log = logging.getLogger(__name__)


class llm(agent):
    def __init__(self, api_key: str, **config):
        format_kwargs(config, api_key=api_key, type="llm")
        super().__init__(**config)
        log.debug("Initializing agent...")

        self.__llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            api_key=api_key,
        )

        self._is_planner = get_optional(config, "planning", False)
        self._prompt_config = Prompt.from_dict(config.get("prompt", {"file": "prompts/defaults/planning.txt" if self._is_planner else "prompts/defaults/agent.txt"}))
        self._prompt = get_prompt(self._prompt_config.file)

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

    def _parse(self, agent_output: str) -> Tuple[str, Optional[dict], bool]:
        """
        Parse a ReAct-style agent output and extract either:
        - (thought, action_dict, False) if Action is present
        - (final_answer, None, True) if Final Answer is present
        - (raw_output, None, False) if nothing structured is found
        """
        # Handle Final Answer
        final_answer_match = re.search(r"Final Answer:\s*(.*)", agent_output, re.DOTALL)
        if final_answer_match:
            final_answer = final_answer_match.group(1).strip()
            return final_answer, None, True

        # Match Thought up to Action or Final Answer or end
        thought_match = re.search(r"Thought:\s*(.*?)(?=\s*Action:|\s*Final Answer:|$)", agent_output, re.DOTALL)
        action_match = re.search(
            r"Action:\s*(\{.*?\})(?=\s*(Thought:|Action:|Observation:|Final Answer:|$))",
            agent_output,
            re.DOTALL
        )

        thought = ""
        if thought_match:
            thought = thought_match.group(1).strip()

        if not action_match:
            return (thought or agent_output.strip(), None, False)

        action_str = action_match.group(1).strip()
        cleaned_action_str = action_str.replace("\r", "").replace("\u200b", "").strip()

        try:
            action = json.loads(cleaned_action_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in action: {e.msg}\nRaw string: {repr(cleaned_action_str)}")

        return thought, action, False


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
        # # Search cache for similar results
        # if self._cache_mode:
        #     closest_query = self._cache_search_actions(query)
        #     if closest_query["score"] > 0.90:
        #         log.debug("Cache hit!")
        #         return self._output.execute(self._generate_workflow(query, closest_query))
        self._task_m.start_workflow(query)

        # Build tool documentation string
        tool_documentation = ""
        for obj in self._tools:
            tool_documentation += f"tool name: {obj.name}\ntool type: {obj.type}\n{obj.description}\n\n\n"

        log.debug(f"[DOCUMENTATION]:\n{tool_documentation}")

        system_prompt = (
            "Here are the available tools:\n"
            "{tools}\n\n"
        ).format(tools=tool_documentation) + self._prompt

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )

        chain = prompt | self.__llm

        current_prompt = query

        for iteration in range(10):
            log.debug(f"\n--- Iteration {iteration + 1} ---")
            result = chain.invoke({"input": current_prompt}).content
            log.debug(f"[RESULT] {result}")

            thought, action_dict, is_final = self._parse(result)

            if is_final:
                log.debug("Final Answer found.")
                self._task_m.end_workflow()
                return thought
            
            if action_dict is None:
                print(f"Thought: {thought}")
                current_prompt += f"\n\nThought: {thought}\n\nContinue with the next step:"
                continue

            log.debug(f"Thought: {thought}")
            log.debug(f"Action: {action_dict}")
            print(f"Thought: {thought}")

            action = Action.from_dict(action_dict)
            observation = self._task_m.execute(action)
            log.debug(f"Observation: {observation}")

            # Append step to ongoing prompt
            current_prompt += f"\n\nThought: {thought}\nAction: {json.dumps(action_dict)}\nObservation: {observation}\n\nContinue with the next step:"

        # # Cache instructions
        # if self._cache_mode:
        #     self._cache_actions(result)
