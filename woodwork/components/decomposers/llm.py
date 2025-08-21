import json
import re
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from typing import Any, Tuple, Optional

from woodwork.components.decomposers.decomposer import decomposer
from woodwork.utils import format_kwargs
from woodwork.types import Action

log = logging.getLogger(__name__)


class llm(decomposer):
    def __init__(self, api_key: str, **config):
        format_kwargs(config, api_key=api_key, type="llm")
        super().__init__(**config)
        log.debug("Initializing decomposer...")

        self.__llm = ChatOpenAI(
            model="gpt-4o-mini",
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

    def _parse(self, agent_output: str) -> Tuple[str, Optional[dict], bool]:
        """
        Parse a ReAct-style agent output and extract either:
        - (thought, action_dict) if Action is present
        - (final_answer, None) if Final Answer is present

        Args:
            agent_output (str): The full output from the agent.

        Returns:
            Tuple[str, Optional[dict]]:
                - If Action is present: (thought, action_dict)
                - If Final Answer is present: (final_answer, None)

        Raises:
            ValueError: if neither an Action nor Final Answer can be found.
        """
        # Handle Final Answer
        final_answer_match = re.search(r"Final Answer:\s*(.*)", agent_output, re.DOTALL)
        if final_answer_match:
            final_answer = final_answer_match.group(1).strip()
            return final_answer, None, True

        # Extract Thought
        thought_match = re.search(r"Thought:\s*(.*)", agent_output)
        if not thought_match:
            raise ValueError("Could not find 'Thought:' line.")
        thought = thought_match.group(1).strip()

        # Extract Action
        action_match = re.search(r"Action:\s*(\{.*\})", agent_output)
        if not action_match:
            raise ValueError("Could not find valid JSON 'Action:' block.")

        action_str = action_match.group(1).strip()
        # Strip out common invisible or problematic characters
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

    def reflect(self, query: str, plan: dict, execution_output: str) -> str | None:
        """
        Reflect on whether the execution output sufficiently answers the original query.

        Args:
            query (str): The original user input.
            plan (dict): The action plan that was generated.
            execution_output (str): The result of executing the action plan.

        Returns:
            str | None: A follow-up prompt to improve the plan, or None if the result is sufficient.
        """
        # Safety fallback for non-dict plan
        try:
            plan_str = json.dumps(plan, indent=2)
        except Exception:
            plan_str = str(plan)

        reflection_prompt = (
            "You are a helpful assistant critically reviewing the result of an executed action plan.\n\n"
            "Here is the original user query:\n"
            f"{query}\n\n"
            "Here is the action plan that was generated:\n"
            f"{plan_str}\n\n"
            "And here is the output after executing the plan:\n"
            f"{execution_output}\n\n"
            "Determine if this output fully and accurately answers the user's question.\n"
            "The output should be:\n"
            "- Concise and focused\n"
            "- Formatted as a clear sentence or a brief paragraph (no markdown bullet points or lists)\n"
            "- Avoid unnecessary technical details or code dumps\n"
            "- When file names are requested, include them naturally within a sentence or paragraph, not as bullet points or enumerated lists\n\n"
            "If the output uses markdown bullet points or list formatting, or if it includes multiple mini explanations instead of one clear statement, it is insufficient.\n\n"
            "Examples:\n"
            "Insufficient (because of bullet points):\n"
            '"""\n'
            "- fileA.py handles X\n"
            "- fileB.py handles Y\n"
            '"""\n'
            "Sufficient:\n"
            '"The code files related to voice input handling are fileA.py and fileB.py, which manage recording and keyword detection respectively."\n\n'
            "Answer using a JSON dictionary with the structure:\n"
            "- If sufficient:\n"
            '  {"is_sufficient": true, "suggested_prompt": null, "reason": "The output is concise, clear, and formatted as a single sentence or brief paragraph that directly answers the question without list formatting."}\n'
            "- If not sufficient:\n"
            '  {"is_sufficient": false, "suggested_prompt": "Please provide a concise sentence or brief paragraph that directly answers the question, including relevant file names naturally, without markdown bullet points or lists.", "reason": "The output uses markdown bullet points, lists, or multiple mini explanations instead of a single clear statement."}\n\n'
            "Be strict and only mark outputs as sufficient if they meet these criteria."
        )

        result = self.__llm.invoke(reflection_prompt).content.strip()
        result = self.__clean(result)
        print(f"[REFLECTION RESULT] {result}")

        if result["is_sufficient"]:
            return None
        else:
            new_plan_prompt = (
                f"The execution output was not sufficient to fully answer the user's query: {query}\n\n"
                f"Here is the previous action plan that was generated:\n{json.dumps(plan, indent=2)}\n\n"
                f"Here is the output after executing that plan:\n{execution_output}\n\n"
                f"Upon reflection, the reason this output was not sufficient is:\n{result['reason']}\n\n"
                "Please generate a new action plan that better addresses the user's request.\n"
                "IMPORTANT GUIDELINES:\n"
                "- If the needed information is already present in the execution output (e.g., filenames or summaries), do NOT use shell or 'line' tool commands just to echo or re-print this known information.\n"
                "- Instead, use the LLM tool or equivalent to directly summarise, reformat, or answer based on the existing information.\n"
                "- Use shell or 'line' tool commands only if you need to retrieve new data from the environment or file system that is not already available.\n"
                "- Avoid redundant commands that simply echo known strings.\n"
                "- The new plan should leverage any available data from the previous plan and output, and produce a concise, accurate answer to the user's query.\n\n"
                f"Here is a suggested prompt to help generate this improved plan:\n{result['suggested_prompt']}\n"
            )

            return new_plan_prompt

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

        # Build system prompt
        system_prompt = (
            "You are a reasoning agent that solves user prompts step-by-step using available tools.\n\n"
            "Here are the available tools:\n"
            "{tools}\n\n"
            "At each step, follow this format exactly:\n\n"
            "Thought: [Explain what you're thinking or what needs to be done next. Be concise but logical.]\n"
            'Action: {{"tool": tool_name, "action": function_or_endpoint, "inputs": {{input_variable: variable_name}}, "output": output_variable}}\n'
            "Observation: [This will be provided by the system after the action is executed. Do NOT fabricate or guess the observation.]\n\n"
            "If you need more information to proceed, ask the user a clarifying question:\n"
            "Thought: [Identify what's missing and why you need it.]\n"
            'Action: {{"tool": "ask_user", "action": "ask", "inputs": {{"question": "your question here"}}, "output": "user_response"}}\n'
            "Observation: [The user's response]\n\n"
            "When the task is complete, respond with:\n"
            "Final Answer: [your conclusion or solution]\n\n"
            "Guidelines:\n"
            "- Only one Action per step.\n"
            "- Do not include an Observation unless it is provided to you.\n"
            "- All actions must include: 'tool', 'action', 'inputs', and 'output'.\n"
            "- Inputs in the action must reference variable names, not hardcoded values.\n"
            '  Example: {{"word": "word"}}, not {{"word": "orange"}}.\n'
            "- Always assign the result to an output variable, even if unused.\n"
            "- Do not fabricate or predict the results of an action — wait for the actual observation to be provided by the system.\n\n"
            "Example:\n"
            "User prompt: What is the length of the word orange?\n\n"
            "Thought: I need to find the length of the word provided.\n"
            'Action: {{"tool": "string_utils", "action": "length", "inputs": {{"word": "word"}}, "output": "length"}}\n'
            "Observation: 6\n"
            "Thought: I now know the length of the word.\n"
            "Final Answer: The length of the word 'orange' is 6.\n\n"
            "Begin reasoning now."
        ).format(tools=tool_documentation)

        # Escape for template compatibility
        escaped_prompt = system_prompt.replace("{", "{{").replace("}", "}}")

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", escaped_prompt),
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

            log.debug(f"Thought: {thought}")
            log.debug(f"Action: {action_dict}")
            print(f"Thought: {thought}")

            action = Action.from_dict(action_dict)
            if action.tool == "ask_user":
                return action.inputs["question"]

            observation = self._task_m.execute(action)
            log.debug(f"Observation: {observation}")

            # Append step to ongoing prompt
            current_prompt += f"\n\nThought: {thought}\nAction: {json.dumps(action_dict)}\nObservation: {observation}\n\nContinue with the next step:"

        # # Cache instructions
        # if self._cache_mode:
        #     self._cache_actions(result)
