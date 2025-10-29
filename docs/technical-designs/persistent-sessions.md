# Persistent Sessions: Context-Aware Conversation Architecture

## Problem Statement

Current architecture treats each user input as a **new task**, losing all context between interactions:

```python
# Current flow (async_runtime.py:221-250, llm.py:190-366)
while True:
    user_input = get_input()  # New input
    emit("input.received", user_input)  # Triggers agent.input()
    agent.input(user_input)  # Resets _workflow_variables (line 195)
    # Agent runs, returns "Final Answer"
    # Context is lost, loop continues
```

**Issues:**
1. Agent resets state on each `input()` call (llm.py:194-195)
2. No conversation history - each input is treated as isolated
3. `ask_user` tool is a workaround for mid-task clarification
4. Cannot handle interruptions naturally
5. Session ID exists but is unused (llm.py:213, 366, async_runtime.py:279)

## Existing Infrastructure Analysis

**Already Built:**
- ✅ **UnifiedEventBus** (unified_event_bus.py) - component registry, routing, message delivery
- ✅ **MessageEnvelope** (message_bus/interface.py:32-99) - has `session_id` field
- ✅ **AsyncRuntime** (async_runtime.py) - main event loop and input handling
- ✅ **Component routing** - UnifiedEventBus._routing_table handles component-to-component

**Not Built:**
- ❌ Session object to maintain agent state
- ❌ Conversation history tracking
- ❌ Session-aware input loop
- ❌ Agent that doesn't reset on each input

## Solution: Minimal Session Extension

**Don't build:** SessionManager (UnifiedEventBus already handles routing), separate message queue, new component registry

**Do build:** Lightweight Session wrapper, session-aware input loop

### Architecture

```
┌──────────────────────────────────────────────┐
│        AsyncRuntime (existing)               │
│  _input_loop() modified to:                  │
│    1. Get/create session for input           │
│    2. Append to conversation history         │
│    3. Pass session to agent                  │
└──────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│         Session (new, minimal)               │
│  - conversation_history: List[dict]          │
│  - workflow_variables: dict                  │
│  - current_prompt: str (accumulated context) │
└──────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│      Agent.input() (modified)                │
│  - Accept optional session parameter         │
│  - Don't reset if session provided           │
│  - Append to session history, not reset      │
└──────────────────────────────────────────────┘
```

### Key Changes

#### 1. Minimal Session Object (NEW - ~30 lines)
```python
# woodwork/core/session.py
@dataclass
class ConversationSession:
    """Lightweight session to maintain agent context across inputs"""
    id: str
    conversation_history: List[dict] = field(default_factory=list)
    workflow_variables: dict = field(default_factory=dict)
    current_prompt: str = ""
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    def add_turn(self, role: str, content: str):
        """Add conversation turn"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
        self.last_activity = time.time()
```

#### 2. AsyncRuntime - Session Storage (MODIFY - 5 lines added)
```python
# async_runtime.py
class AsyncRuntime:
    def __init__(self):
        # ... existing init ...
        self._sessions: Dict[str, ConversationSession] = {}  # ADD THIS

    def _get_or_create_session(self, session_id: str) -> ConversationSession:
        """Get existing session or create new one"""
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationSession(id=session_id)
        return self._sessions[session_id]
```

#### 3. AsyncRuntime - Session-Aware Input Loop (MODIFY - 10 lines)
```python
# async_runtime.py:221-250
async def _input_loop(self):
    # ... existing setup ...

    # ADD: Get session
    session_id = "cli_session"
    session = self._get_or_create_session(session_id)

    while self._running:
        user_input = await self._get_user_input(input_component)

        if user_input in ["exit", ";"]:
            break

        # ADD: Track in session
        session.add_turn("user", user_input)

        # MODIFY: Pass session to processing
        await self.process_user_input(user_input, input_component.name, session)
```

#### 4. Agent - Session-Aware Input (MODIFY - llm.py:190-366)
```python
# llm.py
async def input(self, query: str, inputs: dict = None, session: ConversationSession = None):
    # MODIFY: Don't reset if session provided
    if session:
        # Use existing session state
        self._workflow_variables = session.workflow_variables
        current_prompt = session.current_prompt + f"\n\nUser: {query}"
    else:
        # Old behavior for backwards compatibility
        self._workflow_variables = inputs.copy() if inputs else {}
        current_prompt = query

    # ... existing reasoning loop ...

    for iteration in range(1000):
        result = chain.invoke({"input": current_prompt})
        thought, action_dict, is_final = self._parse(result)

        if is_final:
            # ADD: Save session state before returning
            if session:
                session.conversation_history.append({
                    "role": "assistant",
                    "content": thought,
                    "timestamp": time.time()
                })
                session.current_prompt = current_prompt
                session.workflow_variables = self._workflow_variables
            return thought

        # ... existing action processing ...
        current_prompt += f"\n\nThought: {thought}\nAction: {json.dumps(action_dict)}\nObservation: {observation}"

        # CONTINUE ACCUMULATING, DON'T RESET
```

### Benefits

1. **Minimal Code Changes** - ~50 lines total across 3 files
2. **Uses Existing Infrastructure** - No duplicate routing/registry
3. **Backwards Compatible** - Old single-shot mode still works
4. **Context Persistence** - Agent remembers conversation
5. **Natural ask_user** - User responses are just next turn in conversation

## Test-Driven Development Plan

### Phase 1: ConversationSession Object

**Test 1.1: Create Session**
```python
def test_create_session():
    from woodwork.core.session import ConversationSession

    session = ConversationSession(id="test-123")

    assert session.id == "test-123"
    assert len(session.conversation_history) == 0
    assert len(session.workflow_variables) == 0
```

**Test 1.2: Add Conversation Turns**
```python
def test_add_turns():
    session = ConversationSession(id="test")

    session.add_turn("user", "Hello")
    session.add_turn("assistant", "Hi there")

    assert len(session.conversation_history) == 2
    assert session.conversation_history[0]["role"] == "user"
    assert session.conversation_history[1]["content"] == "Hi there"
```

### Phase 2: AsyncRuntime Session Storage

**Test 2.1: Get or Create Session**
```python
async def test_runtime_get_or_create_session():
    runtime = AsyncRuntime()

    session1 = runtime._get_or_create_session("sess-1")
    session2 = runtime._get_or_create_session("sess-1")  # Same ID

    assert session1.id == session2.id
    assert session1 is session2  # Same object
```

**Test 2.2: Multiple Sessions Isolated**
```python
async def test_multiple_sessions():
    runtime = AsyncRuntime()

    session1 = runtime._get_or_create_session("sess-1")
    session2 = runtime._get_or_create_session("sess-2")

    session1.add_turn("user", "Message 1")
    session2.add_turn("user", "Message 2")

    assert len(session1.conversation_history) == 1
    assert len(session2.conversation_history) == 1
    assert session1.conversation_history[0]["content"] != session2.conversation_history[0]["content"]
```

### Phase 3: Agent Session-Aware Input

**Test 3.1: Agent Without Session (Backwards Compat)**
```python
async def test_agent_without_session():
    agent = create_test_agent()

    result = await agent.input("What is 2+2?")

    assert result is not None
    # No session, old behavior
```

**Test 3.2: Agent With Session Maintains Context**
```python
async def test_agent_with_session():
    agent = create_test_agent()
    session = ConversationSession(id="test")

    # First input
    await agent.input("My name is Alice", session=session)

    # Second input - should remember
    result = await agent.input("What's my name?", session=session)

    assert "Alice" in result
    assert len(session.conversation_history) >= 2
```

**Test 3.3: Agent Session Preserves Variables**
```python
async def test_agent_preserves_workflow_variables():
    agent = create_test_agent()
    session = ConversationSession(id="test")

    # First input creates workflow variable
    await agent.input("Set variable x to 10", session=session)

    assert "x" in session.workflow_variables
    assert session.workflow_variables["x"] == 10

    # Second input should still have access
    result = await agent.input("What is x?", session=session)

    assert "10" in result
```

### Phase 4: Integration Test

**Test 4.1: Full Conversation Flow**
```python
async def test_full_conversation_flow():
    runtime = AsyncRuntime()
    # ... setup components ...

    session = runtime._get_or_create_session("cli")

    # Turn 1
    session.add_turn("user", "My favorite color is blue")
    # Simulate: await runtime.process_user_input(...)
    # Agent processes and responds

    # Turn 2
    session.add_turn("user", "What's my favorite color?")
    # Simulate: await runtime.process_user_input(...)

    # Verify context maintained
    assert len(session.conversation_history) >= 4  # 2 user + 2 assistant
```

**Test 4.2: Command Line ask_user Replacement**
```python
async def test_ask_user_via_conversation():
    """When agent needs info, just returns question as Final Answer"""
    agent = create_test_agent()
    session = ConversationSession(id="test")

    # Agent encounters missing info
    result = await agent.input("Configure server", session=session)

    # Agent asks question instead of using ask_user tool
    assert "?" in result  # Question returned as final answer

    # User responds in next turn
    result = await agent.input("Port 8080", session=session)

    assert "8080" in result
```

## Implementation Order

1. **ConversationSession** (tests 1.1-1.2) - ~30 lines
   - Create `woodwork/core/session.py`
   - Simple dataclass with history tracking

2. **AsyncRuntime Session Storage** (tests 2.1-2.2) - ~10 lines
   - Add `_sessions` dict to `__init__`
   - Add `_get_or_create_session()` method

3. **AsyncRuntime Input Loop** - ~15 lines
   - Modify `_input_loop()` to get/create session
   - Pass session to `process_user_input()`
   - Modify `process_user_input()` signature

4. **Agent Session Support** (tests 3.1-3.3) - ~20 lines
   - Add `session` parameter to `agent.input()`
   - Conditional: if session, use session state; else old behavior
   - Save state back to session before returning

5. **Integration Testing** (tests 4.1-4.2)
   - Test full conversation flow
   - Verify ask_user replacement works

6. **Remove ask_user** (optional, later)
   - Delete `_ask_user_via_events` method
   - Remove event bus registration for user.input.response
   - Update prompts to not mention ask_user tool

## Migration Strategy

**No Feature Flag Needed** - Backwards compatible by default:
- Old code: `agent.input(query)` - works as before
- New code: `agent.input(query, session=session)` - persistent context

**API Input Integration**:
- api_input.py already has WebSocketSession (line 29)
- Extend to use ConversationSession for context
- session_id from WebSocket maps to ConversationSession.id

## Open Questions

1. **Session Timeout**: Auto-cleanup after 30min inactivity?
2. **History Limits**: Truncate to last N tokens when context grows?
3. **Session Persistence**: Save to disk for recovery after restart?

## Success Criteria

- [ ] All 8 tests pass
- [ ] ~75 lines of code added total
- [ ] No existing tests break (backwards compat)
- [ ] Command line remembers context across inputs
- [ ] ask_user tool can be replaced with natural conversation
