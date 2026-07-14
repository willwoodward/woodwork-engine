"""
AgentLoop — pure ReAct execution core.

No Component base class, no event bus wiring, no session management.
Those concerns belong to LLMAgent (the Component wrapper).

The loop expects:
  - an LLM with  async call(system_prompt, history, query) -> str
  - a ToolRegistry
  - an EventBus (per-agent)
"""

import json
import logging
import re
import uuid
from typing import Any, Dict, Optional, Tuple

import tiktoken

from woodwork.core.events import EventBus
from woodwork.core.tools import ToolRegistry
from woodwork.core.types import AgentContext, Step

log = logging.getLogger(__name__)

# Max context tokens before we summarise
_MAX_TOKENS = 90_000
# Give up after this many iterations without a final answer
_MAX_ITERATIONS = 25
# Force final answer after N consecutive thought-only iterations
_MAX_NO_ACTION = 3


class AgentLoop:
    """
    Pure ReAct loop: think → act → observe → repeat.

    Emits events on the provided EventBus for observability.
    """

    def __init__(self, llm: Any, registry: ToolRegistry, event_bus: EventBus) -> None:
        self._llm = llm
        self._registry = registry
        self._event_bus = event_bus

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def run(self, ctx: AgentContext, system_prompt: str) -> str:
        """
        Run the ReAct loop for *ctx* and return the final answer string.

        *system_prompt* should already include the tool documentation.
        """
        current_prompt = ctx.query
        consecutive_no_action = 0

        for iteration in range(_MAX_ITERATIONS):
            log.debug("[AgentLoop] Iteration %d", iteration + 1)

            # Compress if needed
            if _token_count(system_prompt + current_prompt) > _MAX_TOKENS:
                current_prompt = await self._summarise(current_prompt)

            # Call LLM
            raw = await self._llm.call(system_prompt, "", current_prompt)
            log.debug("[AgentLoop] LLM output: %s", raw[:200])

            thought, action_dict, is_final = _parse(raw)

            if is_final:
                log.debug("[AgentLoop] Final answer reached")
                await self._event_bus.emit("agent.step_complete", {"step": iteration + 1})
                return thought

            if action_dict is None:
                consecutive_no_action += 1
                if consecutive_no_action >= _MAX_NO_ACTION:
                    log.warning("[AgentLoop] Forcing final answer after %d thought-only iterations", consecutive_no_action)
                    return thought
                current_prompt += (
                    f"\n\nThought: {thought}\n\n"
                    "You must now either use a tool (Action) or provide your Final Answer. "
                    "Do not respond with only a Thought."
                )
                continue

            consecutive_no_action = 0
            await self._event_bus.emit("agent.thought", {"thought": thought})

            # Pipe may transform action
            action_payload = await self._event_bus.emit("agent.action", {"action": action_dict})
            if isinstance(action_payload, dict) and "action" in action_payload:
                action_dict = action_payload["action"]

            tool_name = action_dict.get("tool", "")
            action_name = action_dict.get("action", "")
            inputs = action_dict.get("inputs", {})
            output_var = action_dict.get("output", "")

            # Resolve variable references
            inputs = _resolve_vars(inputs, ctx.variables)

            await self._event_bus.emit("tool.call", {"tool": tool_name, "args": inputs})

            observation = await self._call_tool(tool_name, action_name, inputs, ctx)

            # Store output variable
            if output_var:
                ctx.variables[output_var] = observation

            # Truncate huge observations
            if _token_count(str(observation)) > 15_000:
                observation = f"[Output truncated — was {_token_count(str(observation))} tokens]"

            obs_str = observation if isinstance(observation, str) else json.dumps(observation)

            await self._event_bus.emit("tool.observation", {"tool": tool_name, "observation": obs_str})

            ctx.steps.append(
                Step(
                    thought=thought,
                    tool=tool_name,
                    action=action_name,
                    inputs=inputs,
                    observation=obs_str,
                    output_var=output_var,
                )
            )

            current_prompt += (
                f"\n\nThought: {thought}"
                f"\nAction: {json.dumps(action_dict)}"
                f"\nObservation: {obs_str}"
                "\n\nContinue with the next step:"
            )

            await self._event_bus.emit("agent.step_complete", {"step": iteration + 1})

        log.warning("[AgentLoop] Max iterations reached without final answer")
        return current_prompt.split("\n")[-1] or "No answer produced."

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    async def _call_tool(self, tool_name: str, action: str, inputs: Dict[str, Any], ctx: AgentContext) -> Any:
        """Execute a tool, handling built-ins and registry tools."""
        if tool_name == "ask_user":
            return await self._ask_user(inputs.get("question", "Please provide input:"), ctx)

        try:
            return await self._registry.execute(tool_name, action, inputs)
        except Exception as exc:
            log.error("[AgentLoop] Tool '%s' error: %s", tool_name, exc)
            await self._event_bus.emit("agent.error", {"error": str(exc), "tool": tool_name})
            return f"Error executing tool '{tool_name}': {exc}"

    async def _ask_user(self, question: str, ctx: AgentContext) -> str:
        """Request user input via event bus."""
        request_id = str(uuid.uuid4())
        import asyncio

        future: asyncio.Future[str] = asyncio.get_event_loop().create_future()

        async def _on_response(payload: Any) -> None:
            rid = payload.get("request_id") if isinstance(payload, dict) else getattr(payload, "request_id", None)
            if rid == request_id and not future.done():
                resp = payload.get("response") if isinstance(payload, dict) else getattr(payload, "response", "")
                future.set_result(resp)

        self._event_bus.register_hook("user.input.response", _on_response)
        await self._event_bus.emit(
            "user.input.request",
            {"question": question, "request_id": request_id, "session_id": ctx.session_id},
        )

        try:
            return await asyncio.wait_for(future, timeout=600)
        except asyncio.TimeoutError:
            return "[Timeout: no user response]"

    async def _summarise(self, context: str) -> str:
        """Compress an over-long context string via the LLM."""
        system = "You are a helpful assistant that summarises context for another agent."
        query = (
            "Summarise the following context into a concise form that retains all important "
            f"facts, goals, decisions, and observations:\n\n{context}"
        )
        summary = await self._llm.call(system, "", query)
        return f"Summary of previous context:\n{summary}\n\nContinue reasoning from here."


# ------------------------------------------------------------------ #
# Pure parsing helpers (no I/O)                                       #
# ------------------------------------------------------------------ #

def _parse(agent_output: str) -> Tuple[str, Optional[dict], bool]:
    """
    Parse ReAct-style output.

    Returns (thought_or_answer, action_dict_or_None, is_final).
    """
    final_match = re.search(r"Final Answer:\s*(.*)", agent_output, re.DOTALL)
    thought_match = re.search(r"Thought:\s*(.*?)(?=\s*Action:|\s*Final Answer:|$)", agent_output, re.DOTALL)
    action_match = re.search(
        r"Action:\s*(\{.*\})(?=\s*(Thought:|Action:|Observation:|Final Answer:|$))",
        agent_output,
        re.DOTALL,
    )

    thought = thought_match.group(1).strip() if thought_match else ""

    if final_match and not action_match:
        return final_match.group(1).strip(), None, True

    if not action_match:
        return (thought or agent_output.strip()), None, False

    action_str = _extract_json_object(action_match.group(1).strip().replace("\r", "").replace("\u200b", ""))
    try:
        action = json.loads(action_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in action: {exc.msg}\nRaw: {action_str!r}") from exc

    return thought, action, False


def _extract_json_object(s: str) -> str:
    """Extract the outermost balanced JSON object from a string."""
    start = s.find("{")
    if start == -1:
        return s
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(s)):
        c = s[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return s


def _resolve_vars(inputs: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
    """Replace string values that match variable names with their stored values."""
    resolved = {}
    for k, v in inputs.items():
        resolved[k] = variables[v] if isinstance(v, str) and v in variables else v
    return resolved


def _token_count(text: str) -> int:
    try:
        enc = tiktoken.encoding_for_model("gpt-4o-mini")
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text if isinstance(text, str) else str(text)))
