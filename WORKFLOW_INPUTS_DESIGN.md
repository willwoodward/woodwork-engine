# Workflow Input Variables - Technical Design

## Problem
Workflows are currently stored with literal prompt text (e.g., "Can you read all emails from Bob"), making them non-reusable. We need parameterized workflows that can accept input variables.

## Solution

### 1. Prompt Variable Extraction (Pipe)
Add a pipe on `input.received` that:
- Detects named entities/variables in the prompt using simple pattern matching or LLM extraction
- Replaces literal values with `{variable_name}` placeholders
- Stores both the original prompt and parameterized prompt in workflow metadata

**Example:**
```
Input: "Can you read all emails from Bob"
Output: "Can you read all emails from {name}"
Variables: { name: "Bob" }
```

### 2. Backend Changes

**Workflow Storage** (Neo4j):
- Add `original_prompt` and `parameterized_prompt` fields to Workflow nodes
- Add `input_variables` JSON field: `{"name": "Bob", "email_count": "5"}`
- Add `variable_schema` JSON field: `{"name": "string", "email_count": "number"}`

**Workflow Execution**:
- When executing a stored workflow, substitute variables in actions
- Already implemented via `_resolve_action_inputs()` in `llm.py` (line 331-347)
- Extend to also substitute in the initial prompt

### 3. Frontend Changes

**Workflow Browser**:
- Show input variables as badges/tags on workflow cards
- Display parameterized prompt instead of original prompt
- Add "Use with different inputs" button

**Workflow Execution Dialog**:
- When clicking a workflow, show input form if it has variables
- Text inputs for each variable
- Pre-fill with original values as defaults
- Execute workflow with new variable values

### 4. Implementation Steps

1. **Backend**: Create `extract_workflow_variables` pipe for `input.received`
   - Use regex or simple NER to extract variables
   - Store in workflow metadata

2. **Backend**: Update workflow storage to include variable schema

3. **Backend**: Update workflow executor to substitute variables in prompts

4. **Frontend**: Display variables in workflow browser

5. **Frontend**: Add input form dialog for variable substitution

## Example Flow

```
User: "Can you read all emails from Bob sent in the last 5 days"

Pipe extracts:
  parameterized_prompt: "Can you read all emails from {name} sent in the last {days} days"
  variables: { name: "Bob", days: "5" }
  schema: { name: "string", days: "number" }

Stored in Neo4j as reusable workflow.

Later, user selects workflow from browser:
  - Form shows: name [Bob], days [5]
  - User changes to: name [Alice], days [7]
  - Workflow executes with new values
```

## Technical Notes

- Use `_workflow_variables` dict already present in `llm.py`
- Variable resolution already works for action inputs via `_resolve_action_inputs()`
- Need to extend resolution to initial prompt text
- Keep original prompt for display/context
