# Workflow Execution as Tools - Technical Design

## Problem
Workflows are currently injected as text context, but agents can't directly execute them as tools. We want agents to be able to call `tool: workflow, action: <workflow_name>, inputs: {...}` to execute stored workflows.

## Solution

### Current State (Already Implemented!)
Looking at the code, this is **already implemented** in `workflows.py`:

1. **Tool Registration** (line 177-198):
   - `execute_workflow` tool is already registered
   - Takes `workflow_id` and `inputs` parameters
   - Exposed to agent's tool list

2. **Workflow Injection** (line 259-283):
   - Top 3 similar workflows already injected into prompt
   - Agent told it can use `execute_workflow(workflow_id, inputs)`

3. **Execution** (line 200-212):
   - `_execute_workflow_tool` already handles execution
   - Uses `WorkflowExecutor` to run workflows with variable substitution

### What's Missing - Make it Match Tool Format

The agent needs to call workflows using the standard tool format:
```json
{
  "tool": "workflow",
  "action": "<workflow_name or workflow_id>",
  "inputs": {"name": "Alice", "days": "7"}
}
```

Instead of the current:
```python
execute_workflow(workflow_id="abc-123", inputs={"name": "Alice"})
```

### Implementation Steps

1. **Add "workflow" as a pseudo-tool** in agent's tool list
   - Register alongside other tools (apis, code, etc.)
   - Description: "Execute a saved workflow by name or ID"
   - Schema defines workflow_id/name and inputs

2. **Update workflow injection context** to show workflows as callable tools:
   ```
   Available workflows you can execute:
   - "Email Summary Workflow" (ID: abc-123) - summarise {name}'s messages
     Call with: tool: workflow, action: "Email Summary Workflow", inputs: {name: "Bob"}
   ```

3. **Add workflow tool parser** in agent action handling:
   - When `tool == "workflow"`, extract workflow name/ID from `action`
   - Map workflow name to workflow_id (lookup in Neo4j by name or parameterized_text)
   - Call `_execute_workflow_tool(workflow_id, inputs)`

4. **Update `_check_similar_workflows_pipe`** to inject workflows as tools:
   - Instead of text context, inject as tool specs
   - Include workflow metadata: name, ID, input schema
   - Show example usage in tool format

### Example Flow

```
User: "summarise Alice's messages"

Pipe finds similar workflow:
  - Name: "Email Summary Workflow"
  - ID: "abc-123"
  - Parameterized: "summarise {name}'s messages"
  - Variables: {name: "Bob"} (original example)

Agent sees in tools:
  tool: workflow
  action: "Email Summary Workflow"
  description: "summarise {name}'s messages"
  parameters: {name: string}

Agent thinks: "I can use the Email Summary Workflow with name=Alice"

Agent outputs:
  {
    "tool": "workflow",
    "action": "Email Summary Workflow",
    "inputs": {"name": "Alice"}
  }

System:
  - Maps "Email Summary Workflow" → workflow_id "abc-123"
  - Calls execute_workflow("abc-123", {"name": "Alice"})
  - Substitutes variables in actions
  - Executes workflow steps
```

## Technical Implementation

### 1. Workflow Tool Registration
```python
# In llm.py or agent.py, add workflow pseudo-tool
{
    "name": "workflow",
    "type": "workflow",
    "description": "Execute a saved workflow by name with custom inputs",
    "parameters": {
        "workflow_name": "Name or ID of workflow to execute",
        "inputs": "Dictionary of input variables for the workflow"
    }
}
```

### 2. Workflow Name Lookup
```python
# In workflows.py
def get_workflow_id_by_name(self, workflow_name: str) -> Optional[str]:
    """Look up workflow ID by name or parameterized text."""
    query = """
    MATCH (w:Workflow)-[:CONTAINS]->(p:Prompt)
    WHERE p.text CONTAINS $name
       OR p.parameterized_text CONTAINS $name
       OR w.id = $name
    RETURN w.id as workflow_id
    LIMIT 1
    """
    result = self._neo4j_component.run(query, {"name": workflow_name})
    if result and len(result) > 0:
        return result[0]["workflow_id"]
    return None
```

### 3. Action Parser for Workflow Tool
```python
# In llm.py action handling
if action_dict.get("tool") == "workflow":
    workflow_name = action_dict.get("action")
    inputs = action_dict.get("inputs", {})

    # Look up workflow ID from name
    workflow_id = self._get_workflow_id_by_name(workflow_name)

    if workflow_id:
        # Execute workflow
        result = await self._execute_workflow_tool(workflow_id, inputs)
        observation = f"Workflow '{workflow_name}' executed successfully"
    else:
        observation = f"Workflow '{workflow_name}' not found"
```

## Benefits

1. **Cleaner syntax** - Workflows are first-class tools
2. **Better discoverability** - Workflows appear alongside other tools
3. **Type safety** - Input schema validation from variable_schema
4. **Consistent interface** - Same tool calling pattern as APIs, code, etc.
5. **Name-based access** - Users can refer to workflows by human-readable names

## Migration Path

This is **backward compatible**:
- Old: `execute_workflow(workflow_id="abc-123", inputs={...})` still works
- New: `tool: workflow, action: "Email Summary", inputs: {...}` also works
- Both use the same underlying `_execute_workflow_tool` implementation
