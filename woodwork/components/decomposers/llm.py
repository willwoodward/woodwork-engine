from woodwork.helper_functions import print_debug, format_kwargs
from woodwork.components.decomposers.decomposer import decomposer

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import json


class llm(decomposer):
    def __init__(self, api_key: str, **config):
        format_kwargs(config, api_key=api_key, type="llm")
        super().__init__(**config)
        print_debug("Initialising decomposer...")

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
            print_debug("Couldn't load array as JSON")
            print_debug(x[start_index : end_index + 1 :])
            return x

    def _find_inputs(self, query: str, inputs: list[str]) -> dict[str, any]:
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

    def _generate_workflow(self, query: str, partial_workflow: dict[str, any]):
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
            "\"\"\"\n"
            "- fileA.py handles X\n"
            "- fileB.py handles Y\n"
            "\"\"\"\n"
            "Sufficient:\n"
            "\"The code files related to voice input handling are fileA.py and fileB.py, which manage recording and keyword detection respectively.\"\n\n"
            "Answer using a JSON dictionary with the structure:\n"
            "- If sufficient:\n"
            '  {\"is_sufficient\": true, \"suggested_prompt\": null, \"reason\": \"The output is concise, clear, and formatted as a single sentence or brief paragraph that directly answers the question without list formatting.\"}\n'
            "- If not sufficient:\n"
            '  {\"is_sufficient\": false, \"suggested_prompt\": \"Please provide a concise sentence or brief paragraph that directly answers the question, including relevant file names naturally, without markdown bullet points or lists.\", \"reason\": \"The output uses markdown bullet points, lists, or multiple mini explanations instead of a single clear statement.\"}\n\n'
            "Be strict and only mark outputs as sufficient if they meet these criteria."
        )

        result = self.__llm.invoke(reflection_prompt).content.strip()
        result = self.__clean(result)
        print_debug(f"[REFLECTION RESULT] {result}")

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
        # Search cache for similar results
        if self._cache_mode:
            closest_query = self._cache_search_actions(query)
            if closest_query["score"] > 0.90:
                print_debug("Cache hit!")
                return self._output.execute(self._generate_workflow(query, closest_query))

        tool_documentation = ""
        for obj in self._tools:
            tool_documentation += f"tool name: {obj.name}\ntool type: {obj.type}\n{obj.description}\n\n\n"

        # print_debug(f"[DOCUMENTATION]:\n{tool_documentation}")
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

        # Clean output as JSON
        result = self.__clean(result)
        print_debug(f"[RESULT] {result}")

        if isinstance(result, str):
            return result

        # Cache instructions
        if self._cache_mode:
            self._cache_actions(result)

        # Send to task_master
        res = self._output.execute(result)
        reflected = self.reflect(query, result, res)
        
        if reflected is not None:
            # print_debug(f"[REFLECTED] {reflected}")
            # If the reflection is not None, it means we need to generate a new plan
            new_plan = self.input(reflected)
            return new_plan

        # Else if no output, print the result
        print(res)
