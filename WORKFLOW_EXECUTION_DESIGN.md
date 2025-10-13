# Workflow Execution via Unified Event Bus

## Problem
Currently, workflows are executed by directly calling components, bypassing the unified event bus. This means:
- Workflow steps don't emit proper lifecycle events
- No hooks/pipes can observe or transform workflow execution
- Inconsistent with how the agent normally executes tools

## Solution
Execute workflows through the unified event bus, treating each workflow step as a standard tool execution.

## Architecture

### Workflow Tool Registration
When similar workflows are found:
1. `WorkflowsFeature._check_similar_workflows_pipe` caches workflows
2. `WorkflowsFeature.get_tools()` returns them as tools with `type: "workflow"`
3. Agent includes workflows in tool documentation

### Workflow Execution Flow
```
Agent decides to use workflow
  ↓
Action: {"tool": "workflow", "action": "workflow_name", "inputs": {...}}
  ↓
Agent._execute_tool_with_improved_api() detects tool == "workflow"
  ↓
Agent._execute_workflow_by_name() looks up workflow ID
  ↓
WorkflowExecutor.execute_workflow() retrieves workflow steps
  ↓
For each step in workflow:
  - Emit "tool.call" event (pipes can transform)
  - Execute step via unified event bus
  - Emit "tool.observation" event (hooks can observe)
  ↓
Return aggregated result
```

### Key Changes Needed

#### 1. WorkflowExecutor Enhancement
**File**: `woodwork/components/internal_features/workflow_executor.py`

```python
async def execute_workflow(self, workflow_id: str, inputs: Dict[str, Any], session_id: str):
    """Execute workflow steps via unified event bus."""
    # Get workflow steps from Neo4j
    steps = self._get_workflow_steps(workflow_id)

    # Substitute input variables
    steps = self._substitute_variables(steps, inputs)

    results = []
    for step in steps:
        # Emit tool.call event
        tool_call = await emit("tool.call", {
            "tool": step.tool,
            "args": step.inputs
        })

        # Execute via component request (goes through event bus)
        result = await self._component_ref.request(
            tool_call.tool,
            {"action": step.action, "inputs": tool_call.args}
        )

        # Emit tool.observation event
        obs = await emit("tool.observation", {
            "tool": step.tool,
            "observation": result
        })

        results.append(obs.observation)

    return {"status": "completed", "results": results}
```

#### 2. Tool Description Format
Make workflow tool descriptions follow standard format:

```
tool name: can you summarise Will's messages
tool type: workflow
<tool_description>
Similarity: 100%
Template: can you summarise {{name}}'s messages
Variables: {{"name": "Will"}}
Steps:
  1. message_reader.read_messages()
  2. langmodel.Summarize(...)

To execute: use tool='workflow', action='can you summarise Will's messages', inputs={{"name": "Will"}}
</tool_description>
```

#### 3. Agent Action Parsing
Agent must recognize workflow type and generate correct action:
```json
{
  "tool": "workflow",
  "action": "can you summarise Will's messages",
  "inputs": {"name": "Will"}
}
```

## Benefits
1. **Consistency**: Workflows execute like any other tool
2. **Observability**: Full event lifecycle for each workflow step
3. **Extensibility**: Hooks/pipes can modify workflow execution
4. **Debugging**: Event bus logs show complete workflow trace

## Implementation Status
- ✅ Workflow discovery and caching
- ✅ Tool registration via `get_tools()`
- ✅ Special handling for `tool == "workflow"`
- ⚠️ WorkflowExecutor needs event bus integration
- ⚠️ Agent needs to correctly parse workflow tool type

## Next Steps
1. Update `WorkflowExecutor.execute_workflow()` to emit events
2. Ensure agent generates `{"tool": "workflow", ...}` actions
3. Test end-to-end workflow execution via event bus
