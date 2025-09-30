import json
import re
import logging
import asyncio
import uuid

from langchain_core.prompts import ChatPromptTemplate
from typing import Any, Tuple, Optional
import tiktoken

from woodwork.components.agents.agent import agent
from woodwork.utils import format_kwargs, get_optional, get_prompt
from woodwork.types import Action, Prompt
from woodwork.core.unified_event_bus import emit, get_global_event_bus
from woodwork.types.event_source import EventSource
from woodwork.components.llms.llm import llm
from woodwork.types.events import UserInputRequestPayload, UserInputResponsePayload
from woodwork.components.internal_features import InternalFeatureRegistry, InternalComponentManager, InternalFeature
from typing import Callable

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

        # Event-based ask_user handling
        self._pending_user_requests: dict[str, asyncio.Future] = {}
        self._event_bus = get_global_event_bus()

        # Register for user input responses
        self._event_bus.register_hook("user.input.response", self._handle_user_input_response)

        # Setup internal features (only for LLM agents)
        self._internal_component_manager = InternalComponentManager()
        self._internal_features = InternalFeatureRegistry.create_features(config)
        self._setup_internal_features(config)

    async def _handle_user_input_response(self, payload):
        """Handle user input response events"""
        try:
            if isinstance(payload, UserInputResponsePayload):
                request_id = payload.request_id
                if request_id in self._pending_user_requests:
                    future = self._pending_user_requests[request_id]
                    if not future.done():
                        future.set_result(payload.response)
                    del self._pending_user_requests[request_id]
                    log.debug(f"[Agent] Received user response for request {request_id}: {payload.response}")
                else:
                    log.warning(f"[Agent] Received user response for unknown request {request_id}")
            elif isinstance(payload, dict) and 'request_id' in payload:
                # Handle dict format for compatibility
                request_id = payload['request_id']
                if request_id in self._pending_user_requests:
                    future = self._pending_user_requests[request_id]
                    if not future.done():
                        future.set_result(payload.get('response', ''))
                    del self._pending_user_requests[request_id]
                    log.debug(f"[Agent] Received user response for request {request_id}: {payload.get('response', '')}")
        except Exception as e:
            log.error(f"[Agent] Error handling user input response: {e}")

    async def _ask_user_via_events(self, question: str, timeout_seconds: int = 600) -> str:
        """Ask user for input via event system instead of blocking input()"""
        request_id = str(uuid.uuid4())

        # Create a future to wait for the response
        future = asyncio.Future()
        self._pending_user_requests[request_id] = future

        try:
            # Create and emit the user input request
            request_payload = UserInputRequestPayload(
                question=question,
                request_id=request_id,
                timeout_seconds=timeout_seconds,
                component_id=self.name,
                component_type="agent"
            )

            log.debug(f"[Agent] Requesting user input: {question}")
            await emit("user.input.request", request_payload)

            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=timeout_seconds)
            log.debug(f"[Agent] User response received: {response}")
            return response

        except asyncio.TimeoutError:
            log.warning(f"[Agent] User input request {request_id} timed out after {timeout_seconds} seconds")
            # Clean up
            if request_id in self._pending_user_requests:
                del self._pending_user_requests[request_id]
            return f"[Timeout: No user response received within {timeout_seconds} seconds]"
        except Exception as e:
            log.error(f"[Agent] Error requesting user input: {e}")
            # Clean up
            if request_id in self._pending_user_requests:
                del self._pending_user_requests[request_id]
            return f"[Error requesting user input: {e}]"

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
        
        # Final Answer takes precedence over thought and action
        if final_answer_match and not action_match:
            final_answer = final_answer_match.group(1).strip()
            return final_answer, None, True

        if not action_match:
            return (thought or agent_output.strip(), None, False)

        action_str = action_match.group(1).strip()
        cleaned_action_str = action_str.replace("\r", "").replace("\u200b", "").strip()

        try:
            action = json.loads(cleaned_action_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in action: {e.msg}\nRaw string: {repr(cleaned_action_str)}")

        return thought, action, False
    
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

        # Set component context for proper event attribution
        EventSource.set_current(getattr(self, 'name', 'unknown_agent'), 'agent')

        # Substitute inputs
        prompt = query
        for key in inputs:
            prompt = prompt.replace(f"{{{key}}}", str(inputs[key]))

        self._task_m.start_workflow(query)

        # Allow input pipes/hooks to transform the incoming query before the main loop
        from woodwork.types.events import InputReceivedPayload
        input_payload = InputReceivedPayload(
            input=query,
            inputs=inputs,
            session_id=getattr(self, "_session", None),
            component_id=self.name,
            component_type="agent"
        )
        transformed = await emit("input.received", input_payload)

        # Extract from typed payload (handle fallback to GenericPayload)
        if hasattr(transformed, 'input'):
            query = transformed.input
            inputs = transformed.inputs
        else:
            # Fallback for GenericPayload
            query = input_payload.input
            inputs = input_payload.inputs

        # Build tool documentation string
        tool_documentation = ""
        for obj in self._tools:
            tool_documentation += f"tool name: {obj.name}\ntool type: {obj.type}\n<tool_description>\n{obj.description}</tool_description>\n\n\n"

        log.debug(f"[DOCUMENTATION]:\n{tool_documentation}")

        system_prompt = (
            "Here are the available tools:\n"
            "{tools}\n\n"
        ).format(tools=tool_documentation) + self._prompt

        log.debug(f"[FULL_CONTEXT]:\n{system_prompt}")
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
            await emit("agent.thought", {"thought": thought})

            # Emit agent.action (pipes can transform, hooks can observe)
            action_payload = await emit("agent.action", {"action": action_dict})
            action_dict = action_payload.action

            try:
                # Create Action from possibly-transformed dict
                action = Action.from_dict(action_dict)

                # Emit tool.call (pipes can transform, hooks can observe)
                tool_call = await emit("tool.call", {"tool": action_dict.get("tool"), "args": action_dict.get("inputs")})

                # Update action if pipes modified it
                if tool_call.tool != action_dict.get("tool") or tool_call.args != action_dict.get("inputs"):
                    action_dict["tool"] = tool_call.tool
                    action_dict["inputs"] = tool_call.args
                    action = Action.from_dict(action_dict)

                # Use improved message bus API for tool execution
                observation = await self._execute_tool_with_improved_api(action)

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
                await emit("agent.error", {"error": e, "context": {"query": query}})
                # feed back a generic observation and continue
                observation = f"An error occurred while executing the action: {e}"

            log.debug(f"Observation: {observation}")

            # Emit tool.observation (pipes can transform, hooks can observe)
            obs = await emit("tool.observation", {"tool": action_dict.get("tool"), "observation": observation})
            observation = obs.observation

            # Append step to ongoing prompt
            current_prompt += f"\n\nThought: {thought}\nAction: {json.dumps(action_dict)}\nObservation: {observation}\n\nContinue with the next step:"

            # Emit step complete
            await emit("agent.step_complete", {"step": iteration + 1, "session_id": getattr(self, "_session", None)})

    async def _execute_tool_with_improved_api(self, action: Action):
        """
        Execute tool using the clean message bus API.

        This leverages the standard MessageBusIntegration methods for
        simple, reliable component-to-component communication.
        """
        try:
            # Special handling for ask_user (uses event-based communication)
            if action.tool == "ask_user":
                question = action.inputs.get('question', 'Please provide input:')
                timeout = action.inputs.get('timeout_seconds', 60)
                return await self._ask_user_via_events(question, timeout)

            # Use the clean message API - one line!
            return await self.request(action.tool, {
                "action": action.action,
                "inputs": action.inputs
            })

        except Exception as e:
            log.error(f"[Agent] Error executing tool '{action.tool}': {e}")
            return f"Error executing tool '{action.tool}': {e}"

    def _setup_internal_features(self, config: dict) -> None:
        """Setup internal features, create required components, and register hooks/pipes."""
        log.debug(f"[LLM Agent {self.name}] Setting up {len(self._internal_features)} internal features")

        for feature in self._internal_features:
            try:
                # Create required components for this feature
                self._create_required_components(feature)

                # Setup the feature with component manager access
                # (This automatically registers hooks and pipes via feature.setup())
                feature.setup(self, config, self._internal_component_manager)

                log.debug(f"[LLM Agent {self.name}] Successfully set up internal feature: {feature.__class__.__name__}")
            except Exception as e:
                log.error(f"[LLM Agent {self.name}] Failed to setup internal feature {feature.__class__.__name__}: {e}")

    def _create_required_components(self, feature: InternalFeature) -> None:
        """Create all components required by a feature."""
        required_components = feature.get_required_components()

        for component_spec in required_components:
            component_id = component_spec["component_id"]
            component_type = component_spec["component_type"]
            component_config = component_spec["config"]
            is_optional = component_spec.get("optional", False)

            try:
                self._internal_component_manager.get_or_create_component(
                    component_id, component_type, component_config
                )
                log.debug(f"[LLM Agent {self.name}] Created internal component: {component_id}")
            except Exception as e:
                if not is_optional:
                    raise RuntimeError(f"Failed to create required internal component {component_id}: {e}")
                log.warning(f"[LLM Agent {self.name}] Failed to create optional internal component {component_id}: {e}")


    def get_internal_component(self, component_id: str):
        """Get an internal component by ID."""
        if hasattr(self, '_internal_component_manager'):
            return self._internal_component_manager.get_component(component_id)
        return None

    def create_component(self, component_type: str, component_id: str = None, **config):
        """
        Direct API to create and attach internal components at runtime.

        Args:
            component_type: Type of component to create (e.g., 'neo4j', 'redis', 'chroma')
            component_id: Optional custom ID, auto-generated if not provided
            **config: Component configuration parameters

        Returns:
            Created component instance

        Example:
            # Create Neo4j component directly
            neo4j = agent.create_component(
                "neo4j",
                uri="bolt://localhost:7687",
                api_key="my-key"
            )

            # Create Redis component
            redis = agent.create_component(
                "redis",
                host="localhost",
                port=6379
            )
        """
        if not hasattr(self, '_internal_component_manager'):
            raise RuntimeError("Internal component manager not available")

        # Auto-generate component ID if not provided
        if component_id is None:
            existing_count = len([k for k in self._internal_component_manager._components.keys()
                                if k.startswith(f"{self.name}_{component_type}")])
            component_id = f"{self.name}_{component_type}_{existing_count}"

        # Add API key from model if available and not provided
        if 'api_key' not in config and hasattr(self, 'model') and hasattr(self.model, '_api_key'):
            config['api_key'] = self.model._api_key

        # Create component through internal manager
        component = self._internal_component_manager.get_or_create_component(
            component_id, component_type, config
        )

        # Auto-attach to agent with clean attribute name
        attr_name = f"_{component_type}_{existing_count}" if existing_count > 0 else f"_{component_type}"
        setattr(self, attr_name, component)

        log.info(f"[LLM Agent {self.name}] Created {component_type} component: {component_id}")
        return component

    def add_hook(self, event_name: str, hook_function, description: str = None):
        """
        Add a hook to this agent that listens for specific events.

        Args:
            event_name: Event to listen for (e.g., 'agent.thought', 'input.received')
            hook_function: Function to call when event occurs
            description: Optional description for debugging

        Example:
            def log_thoughts(payload):
                print(f"Agent thought: {payload.thought}")

            agent.add_hook("agent.thought", log_thoughts, "Log all agent thoughts")
        """
        try:
            from woodwork.core.unified_event_bus import get_global_event_bus
            event_bus = get_global_event_bus()
            event_bus.register_hook(event_name, hook_function)

            desc = f" ({description})" if description else ""
            log.info(f"[LLM Agent {self.name}] Added hook for '{event_name}'{desc}")
        except Exception as e:
            log.error(f"[LLM Agent {self.name}] Failed to add hook for '{event_name}': {e}")

    def add_pipe(self, event_name: str, pipe_function, description: str = None):
        """
        Add a pipe to this agent that can transform event payloads.

        Args:
            event_name: Event to transform (e.g., 'input.received')
            pipe_function: Function that takes payload and returns modified payload
            description: Optional description for debugging

        Example:
            def enhance_input(payload):
                enhanced = f"Enhanced: {payload.input}"
                return payload._replace(input=enhanced)

            agent.add_pipe("input.received", enhance_input, "Add enhancement prefix")
        """
        try:
            from woodwork.core.unified_event_bus import get_global_event_bus
            event_bus = get_global_event_bus()
            event_bus.register_pipe(event_name, pipe_function)

            desc = f" ({description})" if description else ""
            log.info(f"[LLM Agent {self.name}] Added pipe for '{event_name}'{desc}")
        except Exception as e:
            log.error(f"[LLM Agent {self.name}] Failed to add pipe for '{event_name}': {e}")

    def close(self):
        """Clean up internal features and components, then call parent close."""
        try:
            # Teardown features first
            if hasattr(self, '_internal_features'):
                for feature in self._internal_features:
                    try:
                        feature.teardown(self, self._internal_component_manager)
                    except Exception as e:
                        log.warning(f"[LLM Agent {self.name}] Error during feature teardown: {e}")

            # Then cleanup all internal components
            if hasattr(self, '_internal_component_manager'):
                self._internal_component_manager.cleanup_components()
                log.debug(f"[LLM Agent {self.name}] Internal features and components cleaned up")
        except Exception as e:
            log.warning(f"[LLM Agent {self.name}] Error during close: {e}")

        # Call parent close method
        super().close()
