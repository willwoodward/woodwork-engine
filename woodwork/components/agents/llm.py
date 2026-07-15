"""
LLMAgent — Component wrapper around AgentLoop.

Responsibilities:
  - Own a per-agent EventBus (child of the system bus).
  - Build the ToolRegistry from its tool list.
  - Delegate execution to AgentLoop.run().
  - Register hook/pipe configs from the .ww file.
  - Wire internal features (workflows, etc.).
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from woodwork.components.agents.agent import Agent
from woodwork.components.agents.agent_loop import AgentLoop
from woodwork.core.events import EventBus
from woodwork.core.tools import ToolRegistry
from woodwork.core.types import AgentContext
from woodwork.primitives import File
from woodwork.types import Prompt
from woodwork.utils import format_kwargs, get_optional, get_prompt
from woodwork.components.internal_features import InternalFeatureRegistry, InternalComponentManager, InternalFeature

log = logging.getLogger(__name__)


class LLMAgent(Agent):
    def __init__(self, model, system_bus: Optional[EventBus] = None, **config):
        format_kwargs(config, model=model, type="llm")
        super().__init__(**config)

        self._model_component = model
        self._input_component = get_optional(config, "input")

        self._is_planner = get_optional(config, "planning", False)

        # Resolve the system prompt from multiple possible sources:
        #   File("path/to/prompt.txt")  — Python API: appended onto the default ReAct prompt
        #   "inline string"             — Python API: appended onto the default ReAct prompt
        #   {"file": "path"}            — .ww config dict: used as the full prompt (no appending)
        #   missing / None              — default ReAct prompt only
        prompt_arg = config.get("prompt")
        if isinstance(prompt_arg, dict):
            # .ww path — the dict specifies the exact prompt file to use
            self._prompt_config = Prompt.from_dict(prompt_arg)
            self._prompt = get_prompt(self._prompt_config.file)
        else:
            # Python API paths — always start with the default ReAct format
            default = self._load_default_prompt()
            if isinstance(prompt_arg, File):
                try:
                    extra = prompt_arg.read()
                except Exception:
                    extra = ""
                self._prompt = f"{default}\n\n{extra}".strip() if extra else default
            elif isinstance(prompt_arg, str):
                self._prompt = f"{default}\n\n{prompt_arg}".strip() if prompt_arg else default
            else:
                self._prompt = default

        # Per-agent event bus, optionally bubbling to the system bus
        self.event_bus = EventBus(parent=system_bus)

        # Internal features (workflows, etc.)
        self._internal_component_manager = InternalComponentManager()
        self._internal_features: List[InternalFeature] = []
        self._internal_features_config = config
        self._internal_features_setup = False

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def start(self, queue=None, config=None):
        """Set up internal features and build the AgentLoop."""
        if not self._internal_features_setup:
            log.debug("[LLMAgent %s] Setting up internal features...", self.name)

            if queue:
                from woodwork.types import Update

                queue.put(Update(progress=10, component_name=self.name))

            self._internal_features = InternalFeatureRegistry.create_features(self._internal_features_config)

            if queue:
                queue.put(Update(progress=30, component_name=self.name))

            self._setup_internal_features(self._internal_features_config)
            self._internal_features_setup = True

            if queue:
                queue.put(Update(progress=50, component_name=self.name))

        # Register .ww-configured hooks/pipes on this agent's event bus
        self._register_hooks_pipes(self.event_bus)

        log.debug("[LLMAgent %s] Startup complete", self.name)

    def close(self):
        """Tear down internal features."""
        for feature in self._internal_features:
            try:
                feature.teardown(self, self._internal_component_manager)
            except Exception as exc:
                log.warning("[LLMAgent %s] Feature teardown error: %s", self.name, exc)
        self._internal_component_manager.cleanup_components()
        super().close()

    # ------------------------------------------------------------------ #
    # Execution                                                            #
    # ------------------------------------------------------------------ #

    async def execute(self, action: str, inputs: Dict[str, Any]) -> Any:
        """
        Run the agent.

        *action* is typically "run".
        *inputs* should contain at least {"query": "..."}
        and optionally {"session_id": "..."}.
        """
        query = inputs.get("query", action)
        session_id = inputs.get("session_id", "default")
        extra_inputs = {k: v for k, v in inputs.items() if k not in ("query", "session_id")}

        ctx = AgentContext(query=query, session_id=session_id, inputs=extra_inputs)

        # Build registry on every call so dynamic tools (from features) are current
        registry = self._build_registry()

        # Build system prompt with current date + tool docs
        tool_docs = self._build_tool_docs(registry)
        current_date = datetime.now().strftime("%Y-%m-%d %A")
        system_prompt = (
            f"Current date: {current_date}\n\nHere are the available tools:\n{tool_docs}\n\n"
        ) + self._prompt

        loop = AgentLoop(self._model_component, registry, self.event_bus)
        return await loop.run(ctx, system_prompt)

    async def send(self, query: str, session_id: str = "default") -> str:
        """Python API convenience method — send a query and return the response.

        Equivalent to ``await agent.execute("run", {"query": query, "session_id": session_id})``.
        """
        return await self.execute("run", {"query": query, "session_id": session_id})

    # Legacy input() alias kept for existing event-bus delivery paths
    async def input(self, query: str, inputs: Optional[dict] = None):
        inputs = inputs or {}
        return await self.execute("run", {"query": query, **inputs})

    # ------------------------------------------------------------------ #
    # Registry / tool doc helpers                                         #
    # ------------------------------------------------------------------ #

    def _build_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        for tool in self._tools:
            registry.register(tool)

        # Dynamic tools from internal features
        for feature in self._internal_features:
            if hasattr(feature, "get_tools"):
                try:
                    for tool_meta in feature.get_tools():
                        # Wrap feature tool dict in a shim if needed
                        if not hasattr(tool_meta, "name"):
                            tool_meta = _FeatureToolShim(tool_meta, feature)
                        registry.register(tool_meta)
                except Exception as exc:
                    log.debug("[LLMAgent %s] get_tools() error in %s: %s", self.name, feature.__class__.__name__, exc)

        return registry

    def _build_tool_docs(self, registry: ToolRegistry) -> str:
        docs = ""
        for tool in registry.all():
            desc = getattr(tool, "description", "")
            docs += f"tool name: {tool.name}\ntool type: {getattr(tool, 'type', 'tool')}\n<tool_description>\n{desc}</tool_description>\n\n\n"
        return docs

    # ------------------------------------------------------------------ #
    # Internal features                                                   #
    # ------------------------------------------------------------------ #

    def _setup_internal_features(self, config: dict) -> None:
        for feature in self._internal_features:
            try:
                self._create_required_components(feature)
                feature.setup(self, config, self._internal_component_manager, self.event_bus)
                log.debug("[LLMAgent %s] Set up feature: %s", self.name, feature.__class__.__name__)
            except Exception as exc:
                log.error("[LLMAgent %s] Feature setup error in %s: %s", self.name, feature.__class__.__name__, exc)

    def _create_required_components(self, feature: InternalFeature) -> None:
        for spec in feature.get_required_components():
            cid = spec["component_id"]
            ctype = spec["component_type"]
            ccfg = spec["config"]
            optional = spec.get("optional", False)
            try:
                self._internal_component_manager.get_or_create_component(cid, ctype, ccfg)
            except Exception as exc:
                if not optional:
                    raise RuntimeError(f"Failed to create required component {cid}: {exc}") from exc
                log.warning("[LLMAgent %s] Optional component %s unavailable: %s", self.name, cid, exc)

    def _load_default_prompt(self) -> str:
        path = "prompts/defaults/planning.txt" if self._is_planner else "prompts/defaults/agent.txt"
        try:
            return get_prompt(path)
        except Exception:
            return ""

    def get_internal_component(self, component_id: str):
        return self._internal_component_manager.get_component(component_id)


class _FeatureToolShim:
    """Wraps a feature-tool dict so it satisfies the ToolRegistry.register() interface."""

    def __init__(self, meta: dict, feature: Any) -> None:
        self.name: str = meta["name"]
        self.type: str = meta.get("type", "feature_tool")
        self.description: str = meta.get("description", "")
        self._meta = meta
        self._feature = feature

    async def execute(self, action: str, inputs: dict) -> Any:
        if hasattr(self._feature, "_execute_workflow_tool"):
            return await self._feature._execute_workflow_tool(action, inputs)
        raise NotImplementedError(f"Feature tool '{self.name}' has no execute handler")
