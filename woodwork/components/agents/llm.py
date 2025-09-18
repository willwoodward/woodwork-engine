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
from woodwork.components.llms.llm import llm
from woodwork.core.message_bus.interface import create_component_message

log = logging.getLogger(__name__)


class llm(agent):
    def __init__(self, model: llm, **config):
        # Require a model (an LLM component instance or a ChatOpenAI instance) be provided.
        format_kwargs(config, model=model, type="llm")
        super().__init__(**config)
        log.debug("Initializing agent...")

        self._llm = model._llm

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

        chain = prompt | self._llm
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

    async def input(self, query: str, inputs: dict = None):
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

        chain = prompt | self._llm

        current_prompt = query

        for iteration in range(1000):
            log.debug(f"\n--- Iteration {iteration + 1} ---")
            
            current_tokens = system_prompt_tokens + self.count_tokens(current_prompt)
            print(f"tokens: {current_tokens}")

            if current_tokens > 90000:
                log.debug("Token limit reached, summarising context...")

                summariser_prompt = ChatPromptTemplate.from_messages(
                    [
                        ("system", "You are a helpful assistant that summarises context for another agent."),
                        ("human", "Summarise the following context into a concise form that retains all important facts, goals, decisions, and observations:\n\n{context}")
                    ]
                )

                summariser_chain = summariser_prompt | self._llm

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

                # Use message bus for tool execution instead of Task Master
                observation = await self._execute_tool_via_message_bus(action)

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

    async def _execute_tool_via_message_bus(self, action: Action):
        """
        Execute tool via TRUE message bus communication.

        Sends tool execution request as message, waits for response message.
        This implements proper distributed tool communication.
        """
        try:
            # Special handling for ask_user (not a component)
            if action.tool == "ask_user":
                return input(f"{action.inputs.get('question', 'Please provide input:')}\n")
            
            # Execute tool via message bus
            return await self._execute_tool_async(action)

        except Exception as e:
            log.error(f"[Agent] Error executing tool '{action.tool}': {e}")
            return f"Error executing tool '{action.tool}': {e}"

    async def _execute_tool_async(self, action: Action, timeout: float = 5.0) -> str:
        """
        Execute a tool via message bus with clean async response handling.

        Args:
            action: The tool action to execute
            timeout: Maximum time to wait for response (seconds)

        Returns:
            Tool execution result or error message
        """
        if not self._has_message_bus():
            raise RuntimeError(f"Message bus not available for tool '{action.tool}'")

        try:
            # Ensure agent can receive responses - trigger registration if needed
            if not hasattr(self, '_received_responses'):
                self._received_responses = {}
                log.debug(f"[Agent] Agent '{self.name}' checking message bus registration")

                # Force registration to ensure we can receive responses
                if hasattr(self._router, 'message_bus'):
                    from woodwork.core.message_bus.integration import GlobalMessageBusManager
                    bus_manager = GlobalMessageBusManager()
                    bus_manager.register_component(self)
                    log.debug(f"[Agent] Forced registration of agent '{self.name}'")

            # Send request
            log.debug(f"[Agent] Executing tool '{action.tool}' via message bus")
            success, request_id = await self._router.send_to_component_with_response(
                name=action.tool,
                source_component_name=self.name,
                data={"action": action.action, "inputs": action.inputs}
            )

            if not success:
                raise RuntimeError(f"Failed to send request to tool '{action.tool}'")

            # Wait for response
            log.debug(f"[Agent] Waiting for response from '{action.tool}' (request_id: {request_id})")
            result = await self._wait_for_response(request_id, timeout)

            log.debug(f"[Agent] Tool '{action.tool}' completed: {str(result)[:200]}")
            return result

        except Exception as e:
            log.error(f"[Agent] Tool execution failed for '{action.tool}': {e}")
            return f"Error: {e}"

    def _has_message_bus(self) -> bool:
        """Check if message bus is available for tool execution."""
        return hasattr(self, '_router') and self._router is not None

    async def _wait_for_response(self, request_id: str, timeout: float) -> str:
        """
        Wait for a tool response with clean timeout handling.

        Args:
            request_id: Unique request identifier
            timeout: Maximum wait time in seconds

        Returns:
            Tool response result

        Raises:
            TimeoutError: If no response received within timeout
        """
        import asyncio


        poll_interval = 0.05  # 50ms polling
        waited = 0.0

        # Ensure response storage exists
        if not hasattr(self, '_received_responses'):
            self._received_responses = {}

        while waited < timeout:
            if request_id in self._received_responses:
                response_data = self._received_responses.pop(request_id)
                log.debug(f"[Agent] Found response for request_id '{request_id}': {response_data}")
                return response_data["result"]

            if waited % 1.0 < poll_interval:  # Log every second
                log.debug(f"[Agent] Still waiting for response '{request_id}' after {waited:.1f}s, stored responses: {list(self._received_responses.keys())}")

            await asyncio.sleep(poll_interval)
            waited += poll_interval

        # Cleanup failed request
        self._received_responses.pop(request_id, None)
        raise TimeoutError(f"Tool response timeout after {timeout}s")


