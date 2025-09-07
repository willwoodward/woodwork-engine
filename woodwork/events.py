import asyncio
import inspect
import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List

log = logging.getLogger(__name__)

Listener = Callable[[Any], Any]


class EventEmitter:
    """A lightweight event/emitter system with two concepts:

    - Hooks: read-only asynchronous listeners that are fired but do not modify payloads. They are registered
      via on/once and are invoked in the background (errors are logged and emitted via 'agent.error' event).
    - Pipes: blocking transform functions that are invoked sequentially and may modify the payload. They
      can be sync or async and are awaited in sequence when emit_through is used.
    """

    def __init__(self) -> None:
        self._listeners: Dict[str, List[Listener]] = defaultdict(list)
        self._once_listeners: Dict[str, List[Listener]] = defaultdict(list)
        self._pipes: Dict[str, List[Listener]] = defaultdict(list)

    # Hooks API (read-only, async-friendly)
    def on(self, event: str, listener: Listener) -> None:
        self._listeners[event].append(listener)

    def off(self, event: str, listener: Listener) -> None:
        if listener in self._listeners.get(event, []):
            self._listeners[event].remove(listener)
        if listener in self._once_listeners.get(event, []):
            self._once_listeners[event].remove(listener)

    def once(self, event: str, listener: Listener) -> None:
        self._once_listeners[event].append(listener)

    async def emit(self, event: str, payload: Any = None) -> None:
        """Emit an event to hooks. Hooks are invoked but the emitter does not block on them finishing
        (if they are async the coroutine is scheduled as a background task). Exceptions are caught and
        an 'agent.error' event will be emitted if possible.
        """
        # Gather listeners
        listeners = list(self._listeners.get(event, [])) + list(self._once_listeners.get(event, []))

        # clear once-listeners for this emission
        if self._once_listeners.get(event):
            self._once_listeners[event] = []

        for listener in listeners:
            try:
                if inspect.iscoroutinefunction(listener):
                    # schedule background task
                    try:
                        asyncio.create_task(self._safe_call_async(listener, payload))
                    except RuntimeError:
                        # No running loop; run it synchronously
                        await self._safe_call_async(listener, payload)
                else:
                    # sync function: call now but don't await
                    try:
                        listener(payload)
                    except Exception as e:
                        log.exception("Error in sync listener for event %s: %s", event, e)
                        # try to notify via error event
                        if event != "agent.error":
                            try:
                                await self.emit("agent.error", {"error": e, "event": event})
                            except Exception:
                                pass
            except Exception as outer:
                log.exception("Failed to schedule listener for event %s: %s", event, outer)

    async def _safe_call_async(self, listener: Listener, payload: Any) -> None:
        try:
            await listener(payload)
        except Exception as e:
            log.exception("Error in async listener: %s", e)
            # attempt to emit an error event but avoid recursion
            try:
                await self.emit("agent.error", {"error": e})
            except Exception:
                pass

    # Pipes API (blocking transform pipeline)
    def add_pipe(self, event: str, pipe: Listener) -> None:
        """Add a pipe (transformer) for an event. Pipes are executed sequentially by emit_through.
        Each pipe may be sync or async. If it returns a non-None value, that value replaces the payload
        for the next pipe.
        """
        self._pipes[event].append(pipe)

    def remove_pipe(self, event: str, pipe: Listener) -> None:
        if pipe in self._pipes.get(event, []):
            self._pipes[event].remove(pipe)

    async def emit_through(self, event: str, payload: Any = None) -> Any:
        """Run registered pipes for an event sequentially. Each pipe may synchronously return a new payload
        or (if async) return one when awaited. The final payload is returned.
        """
        pipes = list(self._pipes.get(event, []))
        current = payload
        for pipe in pipes:
            try:
                if inspect.iscoroutinefunction(pipe):
                    result = await pipe(current)
                else:
                    result = pipe(current)
                if result is not None:
                    current = result
            except Exception as e:
                log.exception("Error in pipe for event %s: %s", event, e)
                # Emit an agent.error but keep going
                try:
                    await self.emit("agent.error", {"error": e, "event": event})
                except Exception:
                    pass
        return current

    # Synchronous convenience wrappers so code that is not async can still emit safely
    def emit_sync(self, event: str, payload: Any = None) -> None:
        """Emit hooks in a best-effort, synchronous-friendly way.

        - If an event loop is running, schedule emit() as a background task.
        - Otherwise, run emit() to completion using asyncio.run().
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # no running loop
            asyncio.run(self.emit(event, payload))
            return

        # If we have a running loop, create a task to run emit
        try:
            loop.create_task(self.emit(event, payload))
        except Exception:
            # fallback: run emit synchronously using run_until_complete on a new loop
            new_loop = asyncio.new_event_loop()
            try:
                new_loop.run_until_complete(self.emit(event, payload))
            finally:
                new_loop.close()

    def emit_through_sync(self, event: str, payload: Any = None) -> Any:
        """Run pipes synchronously and return the (possibly transformed) payload.
        
        This version runs pipes directly without async overhead to avoid event loop conflicts.
        """
        pipes = list(self._pipes.get(event, []))
        current = payload
        for pipe in pipes:
            try:
                if inspect.iscoroutinefunction(pipe):
                    # For async pipes, we need to handle them carefully
                    try:
                        loop = asyncio.get_running_loop()
                        # If there's a running loop, we can't use run_until_complete
                        # Skip async pipes in sync context for now
                        log.warning(f"Skipping async pipe for event {event} in sync context")
                        continue
                    except RuntimeError:
                        # No running loop, we can use asyncio.run
                        result = asyncio.run(pipe(current))
                        if result is not None:
                            current = result
                else:
                    # Sync pipe - call directly
                    result = pipe(current)
                    if result is not None:
                        current = result
            except Exception as e:
                log.exception("Error in pipe for event %s: %s", event, e)
                # Emit an agent.error but keep going
                try:
                    self.emit_sync("agent.error", {"error": e, "event": event})
                except Exception:
                    pass
        return current

    # Convenience helper methods moved from agent to emitter
    def emit_hook(self, event: str, payload: Any = None) -> None:
        """Emit a non-blocking hook/event in a best-effort way.

        This mirrors the convenience helper previously on the agent. It uses the emitter's
        sync wrapper and logs any failures without raising.
        """
        try:
            try:
                self.emit_sync(event, payload)
            except Exception:
                log.exception("Failed to emit hook %s", event)
        except Exception:
            # swallow any unexpected errors to avoid breaking caller flow
            log.exception("Unexpected error while emitting hook %s", event)

    def emit_pipe_sync(self, event: str, payload: Any = None) -> Any:
        """Run the pipe pipeline for an event and return possibly transformed payload.

        This is a convenience wrapper for emit_through_sync with logging on failure.
        """
        try:
            try:
                return self.emit_through_sync(event, payload)
            except Exception:
                log.exception("Error running pipes for event %s", event)
                return payload
        except Exception:
            log.exception("Unexpected error while running pipes for event %s", event)
            return payload


# Convenience factory
def create_default_emitter() -> EventEmitter:
    return EventEmitter()
