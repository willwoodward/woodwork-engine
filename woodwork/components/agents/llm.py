import json
import re
import logging
import ast

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from typing import Any, Tuple, Optional
import tiktoken

from woodwork.components.agents.agent import agent
from woodwork.utils import format_kwargs, get_optional, get_prompt
from woodwork.types import Action, Prompt
from woodwork.events import emit

log = logging.getLogger(__name__)


class llm(agent):
    def __init__(self, model, **config):
        # Require a model (an LLM component instance or a ChatOpenAI instance) be provided.
        format_kwargs(config, model=model, type="llm")
        super().__init__(**config)
        log.debug("Initializing agent...")

        # Accept either an LLM component (which should expose a property `_llm`) or a ChatOpenAI-like object
        self.__llm = None
        try:
            # If model is a component exposing the `_llm` property (as in openai llm component), use that
            if hasattr(model, "_llm"):
                # property access may raise if not started; allow direct attribute fallback
                try:
                    self.__llm = model._llm
                except Exception:
                    # fallback to underlying attribute if present
                    self.__llm = getattr(model, "_llm_value", None)
            # Or if a ChatOpenAI instance (or similar) is passed directly, use it
            elif isinstance(model, ChatOpenAI):
                self.__llm = model
            else:
                self.__llm = getattr(model, "_llm", None) or getattr(model, "_llm_value", None)
        except Exception:
            self.__llm = None

        if self.__llm is None:
            raise TypeError("Provided model is not a valid LLM component or ChatOpenAI instance for the llm agent.")

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

    def _safe_json_extract(self, s: str):
        try:
            # First try strict JSON
            return json.loads(s)
        except json.JSONDecodeError:
            try:
                # Fallback: allow Python-style literals (True/False/None, single quotes, etc.)
                return ast.literal_eval(s)
            except Exception as e:
                # If both fail, raise a clear error
                raise ValueError(f"Invalid JSON in action: {e}\nRaw string: {repr(s)}")



    def _parse(self, agent_output: str) -> Tuple[str, Optional[dict], bool]:
        """
        Parse a ReAct-style agent output and extract either:
        - (thought, action_dict, False) if Action is present
        - (final_answer, None, True) if Final Answer is present
        - (raw_output, None, False) if nothing structured is found
        """
        # Match Thought up to Action or Final Answer or end
        final_answer_match = re.search(r"Final Answer:\s*(.*)", agent_output, re.DOTALL)
        thought_match = re.search(r"Thought:\s*(.*?)(?=\s*Action:|\s*Final Answer:|$)", agent_output, re.DOTALL)
        action_match = re.search(
            r"Action:\s*(\{.*?\})(?=\s*(Thought:|Action:|Observation:|Final Answer:|$))",
            agent_output,
            re.DOTALL
        )

        thought = ""
        if thought_match:
            thought = thought_match.group(1).strip()
        
        if final_answer_match and not thought_match and not action_match:
            final_answer = final_answer_match.group(1).strip()
            return final_answer, None, True

        if not action_match:
            return (thought or agent_output.strip(), None, False)

        action_str = action_match.group(1).strip()
        cleaned_action_str = action_str.replace("\r", "").replace("\u200b", "").strip()

        try:
            action = self._safe_json_extract(cleaned_action_str)
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
    
    def count_tokens(self, text: str, model: str = "gpt-5-mini"):
        if not isinstance(text, str):
            text = str(text)

        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fall back to a known encoding
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

    def input(self, query: str, inputs: dict = None):
        if inputs is None:
            inputs = {}
        
        # Substitute inputs
        prompt = query
        for key in inputs:
            prompt = prompt.replace(f"{{{key}}}", str(inputs[key]))
        
        # # Search cache for similar results
        # if self._cache_mode:
        #     closest_query = self._cache_search_actions(query)
        #     if closest_query["score"] > 0.90:
        #         log.debug("Cache hit!")
        #         return self._output.execute(self._generate_workflow(query, closest_query))
        self._task_m.start_workflow(query)

        # Allow input pipes/hooks to transform the incoming query before the main loop
        transformed = emit("input.received", {"input": query, "inputs": inputs, "session_id": getattr(self, "_session", None)})
        
        # Extract from typed payload
        query = transformed.input
        inputs = transformed.inputs

        # Build tool documentation string
        tool_documentation = ""
        for obj in self._tools:
            tool_documentation += f"tool name: {obj.name}\ntool type: {obj.type}\n<tool_description>\n{obj.description}</tool_description>\n\n\n"

        log.debug(f"[DOCUMENTATION]:\n{tool_documentation}")

        system_prompt = (
            "Here are the available tools:\n"
            "{tools}\n\n"
        ).format(tools=tool_documentation) + self._prompt

        system_prompt_tokens = self.count_tokens(system_prompt)

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )

        chain = prompt | self.__llm

        current_prompt = query

        for iteration in range(1000):
            log.debug(f"\n--- Iteration {iteration + 1} ---")
            
            current_tokens = system_prompt_tokens + self.count_tokens(current_prompt)
            print(f"tokens: {current_tokens}")

            if current_tokens > 100000:
                log.debug("Token limit reached, summarising context...")

                summariser_prompt = ChatPromptTemplate.from_messages(
                    [
                        ("system", "You are a helpful assistant that summarises context for another agent."),
                        ("human", "Summarise the following context into a concise form that retains all important facts, goals, decisions, and observations:\n\n{context}")
                    ]
                )

                summariser_chain = summariser_prompt | self.__llm

                summary = summariser_chain.invoke({"context": current_prompt}).content
                log.debug(f"[SUMMARY]: {summary}")

                current_prompt = f"Summary of previous context:\n{summary}\n\nContinue reasoning from here."
                system_prompt_tokens = self.count_tokens(system_prompt)
                continue

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

            # Emit agent.thought (non-blocking hook)
            emit("agent.thought", {"thought": thought})

            # Emit agent.action (pipes can transform, hooks can observe)
            action_payload = emit("agent.action", {"action": action_dict})
            action_dict = action_payload.action

            try:
                # Create Action from possibly-transformed dict
                action = Action.from_dict(action_dict)

                # Emit tool.call (pipes can transform, hooks can observe)
                tool_call = emit("tool.call", {"tool": action_dict.get("tool"), "args": action_dict.get("inputs")})
                
                # Update action if pipes modified it
                if tool_call.tool != action_dict.get("tool") or tool_call.args != action_dict.get("inputs"):
                    action_dict["tool"] = tool_call.tool
                    action_dict["inputs"] = tool_call.args
                    action = Action.from_dict(action_dict)

                observation = self._task_m.execute(action)

                observation_tokens = self.count_tokens(observation)
                if observation_tokens > 7500:
                    observation = f"The output from this tool was way too large, it contained {observation_tokens} tokens."

            except KeyError as e:
                log.warning(f"Action dict missing key {e}, feeding back as context.")
                if e == "output":
                    action["output"] = ""
                else:
                    observation = f"Received incomplete action from Agent: {json.dumps(action_dict)}. It is likely missing the key {e}."
            except Exception as e:
                log.exception("Unhandled error while executing action: %s", e)
                # Emit agent.error for unexpected failures
                emit("agent.error", {"error": e, "context": {"query": query}})
                # feed back a generic observation and continue
                observation = f"An error occurred while executing the action: {e}"

            log.debug(f"Observation: {observation}")

            # Emit tool.observation (pipes can transform, hooks can observe)
            obs = emit("tool.observation", {"tool": action_dict.get("tool"), "observation": observation})
            observation = obs.observation

            # Append step to ongoing prompt
            current_prompt += f"\n\nThought: {thought}\nAction: {json.dumps(action_dict)}\nObservation: {observation}\n\nContinue with the next step:"

            # Emit step complete
            emit("agent.step_complete", {"step": iteration + 1, "session_id": getattr(self, "_session", None)})

        # # Cache instructions
        # if self._cache_mode:
        #     self._cache_actions(result)
