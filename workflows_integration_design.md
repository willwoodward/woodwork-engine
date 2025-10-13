# Technical Design: Unified Workflows Integration with Graph Cache

## Executive Summary

This document outlines the design for integrating workflow management into the agent system using Neo4j graph storage. The system will:

1. **Unify `graph_cache` and `workflows` features** into a single `workflows: true` configuration
2. **Auto-capture workflows** as agents execute tasks, building a graph of Prompts → Actions with dependencies
3. **Support manual workflow creation/editing** via the frontend GUI
4. **Enable workflow entrypoints** for direct execution via API routes (e.g., `/workflow/process_data`)
5. **Provide workflows as tools** to agents via similarity-based context injection
6. **Support both direct execution** (via entrypoints) and **agent-guided execution** (as tool suggestions)

## Architecture Overview

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Component                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  workflows: true                                      │  │
│  │  - Auto-creates internal Neo4j component              │  │
│  │  - Registers hooks/pipes for workflow capture         │  │
│  │  - Exposes workflows as callable tools                │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│           WorkflowsFeature (Internal Feature)               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Hooks:                                                │  │
│  │  - agent.action → sync to graph                      │  │
│  │  - agent.step_complete → mark complete               │  │
│  │ Pipes:                                                │  │
│  │  - input.received → inject similar workflows         │  │
│  │ Tools:                                                │  │
│  │  - execute_workflow(workflow_id, inputs)             │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Neo4j Knowledge Base (Auto-created)            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Graph Schema:                                         │  │
│  │  (Workflow)-[:CONTAINS]->(Prompt)                    │  │
│  │  (Workflow)-[:CONTAINS]->(Action)                    │  │
│  │  (Prompt)-[:STARTS]->(Action)                        │  │
│  │  (Action)-[:NEXT]->(Action)                          │  │
│  │  (Action)-[:DEPENDS_ON]->(Action)                    │  │
│  │  (Entrypoint)-[:EXECUTES]->(Workflow)                │  │
│  │                                                       │  │
│  │ Properties:                                           │  │
│  │  - Vector embeddings on Prompt.text, Action.action   │  │
│  │  - Metadata: created_at, status, source (auto/manual)│  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Frontend & API Integration                 │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │ Workflow       │  │ API Input      │  │ GUI Server   │  │
│  │ Browser/Editor │  │ Entrypoints    │  │ REST API     │  │
│  └────────────────┘  └────────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 1. Backend Implementation

### 1.1 Unified Workflows Feature

**File**: `woodwork/components/internal_features/workflows.py`

**Changes**:
- Merge `graph_cache.py` functionality into `workflows.py`
- Remove separate `graph_cache.py` file
- Register as both `workflows` and `graph_cache` (backward compatibility)

**Key Responsibilities**:
1. Auto-create Neo4j component when `workflows: true`
2. Capture workflow execution via hooks/pipes
3. Provide workflow similarity search and context injection
4. Expose workflow execution as tools to agent
5. Support manual workflow CRUD operations

### 1.2 Graph Schema Extensions

**Node Types**:
```cypher
// Existing nodes (keep as-is)
(Workflow {id, status, created_at, completed_at, source: 'auto'|'manual', name, description})
(Prompt {id, text, workflow_id, embedding})
(Action {id, tool, action, inputs, output, sequence, workflow_id, embedding})

// New nodes
(Entrypoint {
  name: string,           // Unique entrypoint name (e.g., 'process_data')
  description: string,    // Human-readable description
  input_schema: json,     // JSON schema for required inputs
  created_at: datetime,
  updated_at: datetime
})
```

**Relationships**:
```cypher
// Existing (keep as-is)
(Workflow)-[:CONTAINS]->(Prompt)
(Workflow)-[:CONTAINS]->(Action)
(Prompt)-[:STARTS]->(Action)
(Action)-[:NEXT]->(Action)
(Action)-[:DEPENDS_ON]->(Action)

// New
(Entrypoint)-[:EXECUTES]->(Workflow)
```

**Constraints & Indices**:
```cypher
CREATE CONSTRAINT entrypoint_name IF NOT EXISTS
  FOR (e:Entrypoint) REQUIRE e.name IS UNIQUE;
CREATE INDEX entrypoint_name_idx IF NOT EXISTS
  FOR (e:Entrypoint) ON (e.name);
CREATE INDEX workflow_source IF NOT EXISTS
  FOR (w:Workflow) ON (w.source);
```

### 1.3 Workflow Execution Engine

**New File**: `woodwork/components/internal_features/workflow_executor.py`

```python
"""Workflow execution engine for direct workflow execution."""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class WorkflowExecutionContext:
    """Context for workflow execution."""
    workflow_id: str
    inputs: Dict[str, Any]
    session_id: str
    execution_id: str
    variables: Dict[str, Any]  # Runtime variables (action outputs)


class WorkflowExecutor:
    """Executes workflows by running action sequences directly."""

    def __init__(self, neo4j_component, task_master):
        """
        Initialize workflow executor.

        Args:
            neo4j_component: Neo4j knowledge base for workflow retrieval
            task_master: TaskMaster for tool/action execution
        """
        self._neo4j = neo4j_component
        self._task_master = task_master

    async def execute_workflow(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        session_id: str
    ) -> Dict[str, Any]:
        """
        Execute a workflow by ID with given inputs.

        Args:
            workflow_id: Workflow ID to execute
            inputs: Input variables for the workflow
            session_id: Session ID for tracking

        Returns:
            Dict with execution results and final outputs
        """
        import uuid

        execution_id = str(uuid.uuid4())
        context = WorkflowExecutionContext(
            workflow_id=workflow_id,
            inputs=inputs,
            session_id=session_id,
            execution_id=execution_id,
            variables=inputs.copy()
        )

        log.info(f"Executing workflow {workflow_id} with execution_id {execution_id}")

        # Get workflow action sequence from Neo4j
        actions = await self._get_workflow_actions(workflow_id)

        if not actions:
            raise ValueError(f"Workflow {workflow_id} has no actions")

        # Execute actions in sequence
        results = []
        for action in actions:
            result = await self._execute_action(action, context)
            results.append(result)

            # Store output in context for dependent actions
            if action.get('output'):
                context.variables[action['output']] = result.get('output')

        return {
            'execution_id': execution_id,
            'workflow_id': workflow_id,
            'status': 'completed',
            'results': results,
            'final_outputs': context.variables
        }

    async def execute_entrypoint(
        self,
        entrypoint_name: str,
        inputs: Dict[str, Any],
        session_id: str
    ) -> Dict[str, Any]:
        """
        Execute workflow via entrypoint name.

        Args:
            entrypoint_name: Name of entrypoint to execute
            inputs: Input variables
            session_id: Session ID for tracking

        Returns:
            Execution results
        """
        # Resolve entrypoint to workflow
        workflow_id = await self._resolve_entrypoint(entrypoint_name)

        if not workflow_id:
            raise ValueError(f"Entrypoint '{entrypoint_name}' not found")

        # Validate inputs against entrypoint schema
        await self._validate_entrypoint_inputs(entrypoint_name, inputs)

        # Execute workflow
        return await self.execute_workflow(workflow_id, inputs, session_id)

    async def _get_workflow_actions(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Get ordered action sequence for workflow."""
        query = """
        MATCH (w:Workflow {id: $workflow_id})-[:CONTAINS]->(a:Action)
        RETURN a.id as id,
               a.tool as tool,
               a.action as action,
               a.inputs as inputs,
               a.output as output,
               a.sequence as sequence
        ORDER BY a.sequence ASC
        """

        result = self._neo4j.run(query, {"workflow_id": workflow_id})
        return result if result else []

    async def _execute_action(
        self,
        action: Dict[str, Any],
        context: WorkflowExecutionContext
    ) -> Dict[str, Any]:
        """Execute a single action using task master."""
        import json

        # Resolve input variables from context
        resolved_inputs = self._resolve_inputs(
            json.loads(action['inputs']) if isinstance(action['inputs'], str) else action['inputs'],
            context.variables
        )

        log.debug(f"Executing action: {action['tool']}.{action['action']} with inputs: {resolved_inputs}")

        # Get tool from task master
        tool = self._task_master.get_tool(action['tool'])

        if not tool:
            raise ValueError(f"Tool '{action['tool']}' not found")

        # Execute tool action
        result = await tool.execute(action['action'], **resolved_inputs)

        return {
            'action_id': action['id'],
            'tool': action['tool'],
            'action': action['action'],
            'output': result,
            'output_var': action.get('output')
        }

    def _resolve_inputs(
        self,
        inputs: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolve input variable references to actual values."""
        resolved = {}

        for key, value in inputs.items():
            if isinstance(value, str) and value in variables:
                # Variable reference - substitute with actual value
                resolved[key] = variables[value]
            else:
                # Literal value
                resolved[key] = value

        return resolved

    async def _resolve_entrypoint(self, entrypoint_name: str) -> Optional[str]:
        """Resolve entrypoint name to workflow ID."""
        query = """
        MATCH (e:Entrypoint {name: $name})-[:EXECUTES]->(w:Workflow)
        RETURN w.id as workflow_id
        LIMIT 1
        """

        result = self._neo4j.run(query, {"name": entrypoint_name})

        if result and len(result) > 0:
            return result[0]['workflow_id']

        return None

    async def _validate_entrypoint_inputs(
        self,
        entrypoint_name: str,
        inputs: Dict[str, Any]
    ) -> None:
        """Validate inputs against entrypoint schema."""
        query = """
        MATCH (e:Entrypoint {name: $name})
        RETURN e.input_schema as schema
        """

        result = self._neo4j.run(query, {"name": entrypoint_name})

        if not result or len(result) == 0:
            return  # No schema to validate against

        schema = result[0].get('schema')

        if not schema:
            return

        # TODO: Implement JSON schema validation
        # For now, just check required fields exist
        import json
        schema_dict = json.loads(schema) if isinstance(schema, str) else schema

        required = schema_dict.get('required', [])
        for field in required:
            if field not in inputs:
                raise ValueError(f"Required input '{field}' missing for entrypoint '{entrypoint_name}'")
```

### 1.4 Workflows as Agent Tools

**Update**: `woodwork/components/internal_features/workflows.py`

Add tool registration to expose workflows to the agent:

```python
def get_tools(self) -> List[Dict[str, Any]]:
    """Return workflow execution tools for the agent."""
    return [
        {
            "name": "execute_workflow",
            "description": "Execute a saved workflow by ID with given inputs",
            "parameters": {
                "workflow_id": {
                    "type": "string",
                    "description": "ID of the workflow to execute"
                },
                "inputs": {
                    "type": "object",
                    "description": "Input variables for the workflow"
                }
            },
            "function": self._execute_workflow_tool
        }
    ]

async def _execute_workflow_tool(self, workflow_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Tool function for agent to execute workflows."""
    if not self._workflow_executor:
        raise ValueError("Workflow executor not initialized")

    # Get current session ID from component ref
    session_id = getattr(self._component_ref, 'session_id', 'default')

    return await self._workflow_executor.execute_workflow(
        workflow_id, inputs, session_id
    )
```

### 1.5 Enhanced Input Pipe for Workflow Context Injection

**Update**: `woodwork/components/internal_features/workflows.py`

Modify `_check_similar_workflows_pipe` to inject top 3 workflows as tools:

```python
def _check_similar_workflows_pipe(self, payload: InputReceivedPayload) -> InputReceivedPayload:
    """Check for similar workflows and inject as tool context."""
    if not self._neo4j_component:
        return payload

    try:
        log.debug(f"Checking for similar workflows for input: {payload.input[:50]}...")

        # Search for similar prompts
        similar_prompts = self._neo4j_component.similarity_search(
            payload.input, "Prompt", "text", limit=3  # Top 3
        )

        if similar_prompts and len(similar_prompts) > 0:
            # Build workflow context with actual action sequences
            workflow_contexts = []

            for i, match in enumerate(similar_prompts, 1):
                similarity_score = match.get("score", 0)

                if similarity_score > 0.75:  # Threshold for relevance
                    workflow_data = self._get_workflow_detail(match.get("nodeID"))

                    if workflow_data:
                        workflow_contexts.append({
                            'rank': i,
                            'similarity': similarity_score,
                            'workflow_id': workflow_data.get('workflow_id'),
                            'name': workflow_data.get('name', f'Workflow {i}'),
                            'description': workflow_data.get('description', ''),
                            'actions': workflow_data.get('actions', [])
                        })

            if workflow_contexts:
                # Inject workflow context into input
                context_text = self._format_workflow_contexts(workflow_contexts)

                enhanced_input = f"""{payload.input}

[Available Similar Workflows]:
{context_text}

You can either:
1. Use execute_workflow(workflow_id, inputs) to run an exact workflow
2. Use the workflow structure as guidance for your own solution
"""

                return replace(payload, input=enhanced_input)

    except Exception as e:
        log.debug(f"Workflow context lookup failed: {e}")

    # Start new workflow tracking
    self._start_new_workflow(payload.input)
    return payload

def _format_workflow_contexts(self, contexts: List[Dict]) -> str:
    """Format workflow contexts for agent consumption."""
    lines = []

    for ctx in contexts:
        lines.append(f"\n{ctx['rank']}. {ctx['name']} (ID: {ctx['workflow_id']}, Similarity: {ctx['similarity']:.0%})")

        if ctx.get('description'):
            lines.append(f"   Description: {ctx['description']}")

        lines.append("   Steps:")
        for j, action in enumerate(ctx['actions'][:5], 1):  # Limit to 5 steps
            lines.append(f"      {j}. {action['tool']}.{action['action']}({action['inputs']}) → {action['output']}")

    return '\n'.join(lines)
```

### 1.6 API Input Entrypoint Integration

**Update**: `woodwork/components/inputs/api_input.py`

Add workflow entrypoint routing:

```python
def __init__(self, name="api_input", **config):
    # ... existing init code ...

    # Workflow entrypoint routes
    self.workflow_entrypoints: Dict[str, str] = config.get("workflow_entrypoints", {})
    # Example: {"process_data": "/workflow/process_data", "analyze": "/workflow/analyze"}

    # Setup workflow routes
    self._setup_workflow_routes()

def _setup_workflow_routes(self):
    """Setup workflow entrypoint routes dynamically."""
    for entrypoint_name, route_path in self.workflow_entrypoints.items():
        self._register_workflow_route(entrypoint_name, route_path)

def _register_workflow_route(self, entrypoint_name: str, route_path: str):
    """Register a single workflow entrypoint route."""

    @self.app.post(route_path)
    async def execute_workflow_entrypoint(request: Request):
        """Execute workflow via entrypoint."""
        try:
            body = await request.json()
            inputs = body.get('inputs', {})
            session_id = body.get('session_id', str(uuid.uuid4()))

            log.info(f"Workflow entrypoint '{entrypoint_name}' triggered with inputs: {inputs}")

            # Get workflow executor from task master or internal features
            executor = self._get_workflow_executor()

            if not executor:
                raise ValueError("Workflow executor not available")

            # Execute workflow
            result = await executor.execute_entrypoint(
                entrypoint_name, inputs, session_id
            )

            return JSONResponse(content={
                'status': 'success',
                'entrypoint': entrypoint_name,
                'result': result
            })

        except Exception as e:
            log.error(f"Workflow entrypoint execution failed: {e}")
            return JSONResponse(
                status_code=500,
                content={'status': 'error', 'error': str(e)}
            )

    log.info(f"Registered workflow entrypoint: {route_path} → {entrypoint_name}")

def _get_workflow_executor(self):
    """Get workflow executor from task master."""
    if hasattr(self, 'task_m') and self.task_m:
        # Access workflow executor through task master's internal component manager
        return getattr(self.task_m, '_workflow_executor', None)
    return None
```

**Example .ww Configuration**:
```python
api = api_input {
    port: 8000
    workflow_entrypoints: {
        "process_data": "/workflow/process_data"
        "analyze_logs": "/workflow/analyze_logs"
    }
}

agent = agent llm {
    workflows: true  # Enables workflow capture and execution
    model: gpt4
    tools: [file_tool, analysis_tool]
}
```

## 2. Frontend Implementation

### 2.1 Workflow CRUD API Routes

**Update**: `woodwork/gui/fastapi_gui_server.py`

Add comprehensive workflow management endpoints:

```python
@self.app.get("/api/workflows/get")
async def get_stored_workflows():
    """Get all stored workflows from Neo4j."""
    workflows = await self._get_all_workflows()
    return workflows

@self.app.get("/api/workflows/{workflow_id}")
async def get_workflow_detail(workflow_id: str):
    """Get detailed workflow with graph structure."""
    workflow = await self._get_workflow_detail(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow

@self.app.post("/api/workflows")
async def create_workflow(request: CreateWorkflowRequest):
    """Create a new manual workflow."""
    workflow_id = await self._create_workflow(
        name=request.name,
        description=request.description,
        actions=request.actions,
        source='manual'
    )
    return {"workflow_id": workflow_id, "status": "created"}

@self.app.put("/api/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, request: UpdateWorkflowRequest):
    """Update existing workflow (manual or auto-captured)."""
    await self._update_workflow(workflow_id, request)
    return {"status": "updated"}

@self.app.delete("/api/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """Delete a workflow."""
    await self._delete_workflow(workflow_id)
    return {"status": "deleted"}

@self.app.post("/api/workflows/{workflow_id}/entrypoint")
async def create_entrypoint(workflow_id: str, request: CreateEntrypointRequest):
    """Create an entrypoint for a workflow."""
    await self._create_entrypoint(
        workflow_id=workflow_id,
        name=request.name,
        description=request.description,
        input_schema=request.input_schema
    )
    return {"status": "created"}

@self.app.post("/api/workflows/{workflow_id}/execute")
async def execute_workflow_api(workflow_id: str, request: ExecuteWorkflowRequest):
    """Execute a workflow via API."""
    result = await self._execute_workflow_via_api(
        workflow_id=workflow_id,
        inputs=request.inputs,
        session_id=request.session_id
    )
    return result
```

### 2.2 React Hooks for Workflow Management

**New File**: `gui/src/hooks/useWorkflowManagement.ts`

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import type { Workflow, WorkflowAction } from '@/types/workflow';

export function useWorkflowManagement() {
  const queryClient = useQueryClient();

  const createWorkflow = useMutation({
    mutationFn: async (data: {
      name: string;
      description: string;
      actions: WorkflowAction[];
    }) => {
      return apiClient.post('/api/workflows', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });

  const updateWorkflow = useMutation({
    mutationFn: async (data: {
      id: string;
      name?: string;
      description?: string;
      actions?: WorkflowAction[];
    }) => {
      const { id, ...updates } = data;
      return apiClient.put(`/api/workflows/${id}`, updates);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });

  const deleteWorkflow = useMutation({
    mutationFn: async (workflowId: string) => {
      return apiClient.delete(`/api/workflows/${workflowId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });

  const createEntrypoint = useMutation({
    mutationFn: async (data: {
      workflowId: string;
      name: string;
      description: string;
      inputSchema: object;
    }) => {
      const { workflowId, ...entrypoint } = data;
      return apiClient.post(`/api/workflows/${workflowId}/entrypoint`, entrypoint);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });

  const executeWorkflow = useMutation({
    mutationFn: async (data: {
      workflowId: string;
      inputs: Record<string, any>;
      sessionId?: string;
    }) => {
      const { workflowId, ...payload } = data;
      return apiClient.post(`/api/workflows/${workflowId}/execute`, payload);
    },
  });

  return {
    createWorkflow,
    updateWorkflow,
    deleteWorkflow,
    createEntrypoint,
    executeWorkflow,
  };
}
```

### 2.3 Workflow Editor Component

**Update**: `gui/src/app/workflows/workflow-builder.tsx`

Add support for:
- Creating new workflows manually
- Editing auto-captured workflows
- Adding/removing/reordering actions
- Creating entrypoints
- Testing workflow execution

```typescript
const handleSaveWorkflow = async () => {
  if (workflowId === "new") {
    // Create new workflow
    await createWorkflow.mutateAsync({
      name: workflowName,
      description: workflowDescription,
      actions: workflowSteps.map((step, idx) => ({
        sequence: idx,
        tool: step.tool,
        action: step.action || step.name,
        inputs: step.inputs || {},
        output: step.output || `step_${idx}_output`,
      })),
    });
  } else {
    // Update existing workflow
    await updateWorkflow.mutateAsync({
      id: workflowId,
      name: workflowName,
      description: workflowDescription,
      actions: workflowSteps.map((step, idx) => ({
        sequence: idx,
        tool: step.tool,
        action: step.action || step.name,
        inputs: step.inputs || {},
        output: step.output || `step_${idx}_output`,
      })),
    });
  }
};

const handleRunWorkflow = async () => {
  // Execute workflow with test inputs
  const testInputs = {}; // Collect from form or use defaults

  await executeWorkflow.mutateAsync({
    workflowId: workflowId!,
    inputs: testInputs,
  });
};

const handleCreateEntrypoint = async () => {
  // Show dialog to create entrypoint
  const entrypointData = {
    workflowId: workflowId!,
    name: entrypointName,
    description: entrypointDescription,
    inputSchema: buildInputSchema(workflowSteps), // Infer from actions
  };

  await createEntrypoint.mutateAsync(entrypointData);
};
```

### 2.4 Workflow Browser Enhancements

**Update**: `gui/src/components/workflows/workflow-browser.tsx`

Add filters and actions:
- Filter by source (auto-captured vs manual)
- Show entrypoint status
- Quick execute button
- Edit button (opens in workflow-builder)

```typescript
<div className="flex gap-2">
  <Button
    size="sm"
    variant="outline"
    onClick={() => setSourceFilter(sourceFilter === 'all' ? 'auto' : 'all')}
  >
    {sourceFilter === 'all' ? 'All' : 'Auto-captured'}
  </Button>

  <Button
    size="sm"
    variant="outline"
    onClick={() => setHasEntrypoint(!hasEntrypoint)}
  >
    {hasEntrypoint ? 'With Entrypoints' : 'All'}
  </Button>
</div>

{workflows.map(workflow => (
  <WorkflowCard
    key={workflow.id}
    workflow={workflow}
    onEdit={() => router.push(`/workflows/edit/${workflow.id}`)}
    onExecute={() => handleQuickExecute(workflow.id)}
    onDelete={() => handleDelete(workflow.id)}
    showEntrypointBadge={workflow.hasEntrypoint}
  />
))}
```

## 3. Test-Driven Development Plan

### 3.1 Unit Tests

**File**: `tests/unit/components/internal_features/test_workflows_feature.py`

```python
import pytest
from unittest.mock import Mock, AsyncMock, patch
from woodwork.components.internal_features.workflows import WorkflowsFeature
from woodwork.components.internal_features.workflow_executor import WorkflowExecutor
from woodwork.types.events import InputReceivedPayload, AgentActionPayload


class TestWorkflowsFeature:
    """Test unified workflows feature."""

    @pytest.fixture
    def mock_component(self):
        component = Mock()
        component.name = "test_agent"
        component.model = Mock()
        component.model._api_key = "test-key"
        return component

    @pytest.fixture
    def mock_neo4j(self):
        neo4j = Mock()
        neo4j.init_vector_index = Mock()
        neo4j.run = Mock(return_value=[])
        neo4j.similarity_search = Mock(return_value=[])
        return neo4j

    @pytest.fixture
    def feature(self):
        return WorkflowsFeature()

    def test_feature_setup_creates_neo4j_component(self, feature, mock_component, mock_neo4j):
        """Test that feature setup creates Neo4j component."""
        component_manager = Mock()
        component_manager.get_or_create_component = Mock(return_value=mock_neo4j)

        feature._setup_feature(mock_component, {}, component_manager)

        component_manager.get_or_create_component.assert_called_once()
        assert hasattr(mock_component, '_workflows_db')
        assert mock_component._workflows_mode is True

    def test_inject_top_3_similar_workflows(self, feature, mock_neo4j):
        """Test that top 3 similar workflows are injected into input."""
        feature._neo4j_component = mock_neo4j

        # Mock 3 similar workflows
        mock_neo4j.similarity_search.return_value = [
            {"nodeID": "p1", "score": 0.95, "text": "Similar task 1"},
            {"nodeID": "p2", "score": 0.88, "text": "Similar task 2"},
            {"nodeID": "p3", "score": 0.80, "text": "Similar task 3"},
        ]

        feature._get_workflow_detail = Mock(side_effect=[
            {"workflow_id": "w1", "name": "Workflow 1", "actions": [{"tool": "t1", "action": "a1", "inputs": {}, "output": "o1"}]},
            {"workflow_id": "w2", "name": "Workflow 2", "actions": [{"tool": "t2", "action": "a2", "inputs": {}, "output": "o2"}]},
            {"workflow_id": "w3", "name": "Workflow 3", "actions": [{"tool": "t3", "action": "a3", "inputs": {}, "output": "o3"}]},
        ])

        payload = InputReceivedPayload(
            input="Process data files",
            inputs={},
            session_id="test",
            component_id="agent",
            component_type="agent"
        )

        result = feature._check_similar_workflows_pipe(payload)

        assert "[Available Similar Workflows]:" in result.input
        assert "Workflow 1" in result.input
        assert "Workflow 2" in result.input
        assert "Workflow 3" in result.input
        assert "execute_workflow" in result.input

    def test_workflow_tools_registered(self, feature):
        """Test that workflow execution tools are registered."""
        tools = feature.get_tools()

        assert len(tools) > 0
        assert any(t['name'] == 'execute_workflow' for t in tools)


class TestWorkflowExecutor:
    """Test workflow executor."""

    @pytest.fixture
    def mock_neo4j(self):
        neo4j = Mock()
        neo4j.run = Mock(return_value=[
            {
                "id": "a1",
                "tool": "file_tool",
                "action": "read",
                "inputs": '{"path": "input_file"}',
                "output": "file_content",
                "sequence": 0
            },
            {
                "id": "a2",
                "tool": "text_tool",
                "action": "process",
                "inputs": '{"text": "file_content"}',
                "output": "processed_text",
                "sequence": 1
            }
        ])
        return neo4j

    @pytest.fixture
    def mock_task_master(self):
        task_master = Mock()

        # Mock tools
        file_tool = Mock()
        file_tool.execute = AsyncMock(return_value="Sample file content")

        text_tool = Mock()
        text_tool.execute = AsyncMock(return_value="Processed text output")

        task_master.get_tool = Mock(side_effect=lambda name: {
            "file_tool": file_tool,
            "text_tool": text_tool
        }.get(name))

        return task_master

    @pytest.fixture
    def executor(self, mock_neo4j, mock_task_master):
        return WorkflowExecutor(mock_neo4j, mock_task_master)

    @pytest.mark.asyncio
    async def test_execute_workflow_runs_action_sequence(self, executor):
        """Test that workflow executor runs actions in sequence."""
        result = await executor.execute_workflow(
            workflow_id="w1",
            inputs={"input_file": "test.txt"},
            session_id="test"
        )

        assert result['status'] == 'completed'
        assert len(result['results']) == 2
        assert 'file_content' in result['final_outputs']
        assert 'processed_text' in result['final_outputs']

    @pytest.mark.asyncio
    async def test_execute_entrypoint_resolves_and_executes(self, executor, mock_neo4j):
        """Test that entrypoint execution resolves to workflow and executes."""
        mock_neo4j.run = Mock(side_effect=[
            # First call: resolve entrypoint
            [{"workflow_id": "w1"}],
            # Second call: validate schema
            [{"schema": '{"required": []}'}],
            # Third call: get actions
            [
                {
                    "id": "a1",
                    "tool": "test_tool",
                    "action": "test_action",
                    "inputs": '{}',
                    "output": "result",
                    "sequence": 0
                }
            ]
        ])

        result = await executor.execute_entrypoint(
            entrypoint_name="process_data",
            inputs={},
            session_id="test"
        )

        assert result['status'] == 'completed'
        assert result['workflow_id'] == 'w1'

    @pytest.mark.asyncio
    async def test_input_variable_resolution(self, executor):
        """Test that action inputs resolve variable references."""
        resolved = executor._resolve_inputs(
            {"file": "file_content", "limit": 100},
            {"file_content": "Sample content", "other": "value"}
        )

        assert resolved['file'] == "Sample content"  # Variable resolved
        assert resolved['limit'] == 100  # Literal preserved
```

### 3.2 Integration Tests

**File**: `tests/integration/components/internal_features/test_workflows_integration.py`

```python
import pytest
from woodwork.components.agents.llm import llm
from woodwork.components.inputs.api_input import api_input
from woodwork.types.events import InputReceivedPayload


class TestWorkflowsIntegration:
    """Integration tests for workflows feature."""

    @pytest.mark.asyncio
    async def test_workflow_auto_capture_and_similarity(self):
        """Test full workflow: capture, store, and retrieve via similarity."""
        # Setup agent with workflows enabled
        # Execute task
        # Verify workflow captured in Neo4j
        # Execute similar task
        # Verify similar workflow injected
        pass

    @pytest.mark.asyncio
    async def test_manual_workflow_creation_and_execution(self):
        """Test creating manual workflow and executing it."""
        # Create workflow via API
        # Execute workflow
        # Verify correct execution
        pass

    @pytest.mark.asyncio
    async def test_entrypoint_api_routing(self):
        """Test API input entrypoint routing."""
        # Setup API input with entrypoint
        # Create workflow with entrypoint
        # Call API route
        # Verify workflow executed
        pass

    @pytest.mark.asyncio
    async def test_workflow_as_agent_tool(self):
        """Test agent using workflow as tool."""
        # Setup agent with workflows
        # Create stored workflow
        # Agent receives input with similar workflow
        # Agent calls execute_workflow tool
        # Verify workflow executed correctly
        pass
```

### 3.3 Frontend Tests

**File**: `gui/src/hooks/__tests__/useWorkflowManagement.test.ts`

```typescript
import { renderHook, waitFor } from '@testing-library/react';
import { useWorkflowManagement } from '../useWorkflowManagement';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

describe('useWorkflowManagement', () => {
  const queryClient = new QueryClient();
  const wrapper = ({ children }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  it('creates workflow successfully', async () => {
    const { result } = renderHook(() => useWorkflowManagement(), { wrapper });

    await result.current.createWorkflow.mutateAsync({
      name: 'Test Workflow',
      description: 'Test description',
      actions: [
        { sequence: 0, tool: 'test_tool', action: 'test_action', inputs: {}, output: 'result' }
      ],
    });

    await waitFor(() => expect(result.current.createWorkflow.isSuccess).toBe(true));
  });

  it('executes workflow successfully', async () => {
    const { result } = renderHook(() => useWorkflowManagement(), { wrapper });

    await result.current.executeWorkflow.mutateAsync({
      workflowId: 'w1',
      inputs: { test: 'input' },
    });

    await waitFor(() => expect(result.current.executeWorkflow.isSuccess).toBe(true));
  });
});
```

## 4. Implementation Phases

### Phase 1: Backend Core (Week 1)
**Tests First**:
1. Write unit tests for `WorkflowExecutor`
2. Write tests for unified `WorkflowsFeature`
3. Implement `WorkflowExecutor` (make tests pass)
4. Merge `graph_cache.py` into `workflows.py`
5. Add entrypoint graph schema

**Deliverable**: Workflow execution engine working with tests passing

### Phase 2: Tool Integration (Week 1)
**Tests First**:
1. Write tests for workflow tools registration
2. Write tests for workflow context injection (top 3 similar)
3. Implement `get_tools()` in WorkflowsFeature
4. Implement enhanced `_check_similar_workflows_pipe`

**Deliverable**: Workflows available as agent tools with similarity-based suggestions

### Phase 3: API Integration (Week 2)
**Tests First**:
1. Write tests for API input entrypoint routing
2. Write tests for workflow execution via API
3. Implement `_setup_workflow_routes()` in api_input
4. Add workflow management endpoints to fastapi_gui_server

**Deliverable**: API routes for workflow entrypoints and management

### Phase 4: Frontend CRUD (Week 2)
**Tests First**:
1. Write tests for useWorkflowManagement hook
2. Write tests for workflow editor actions
3. Implement useWorkflowManagement hook
4. Update workflow-builder with save/edit/delete

**Deliverable**: Full workflow CRUD in frontend

### Phase 5: Integration Testing (Week 3)
**Tests First**:
1. Write end-to-end integration tests
2. Test auto-capture → similarity → tool execution flow
3. Test manual creation → entrypoint → API execution flow
4. Fix any integration issues

**Deliverable**: Fully integrated system with all flows working

### Phase 6: Documentation & Polish (Week 3)
1. Add inline documentation
2. Create user guide for .ww configuration
3. Add example workflows
4. Performance optimization

## 5. Configuration Examples

### 5.1 Agent with Workflows

```python
# my_agent.ww

api = api_input {
    port: 8000
    workflow_entrypoints: {
        "process_data": "/workflow/process_data"
        "analyze_logs": "/workflow/analyze_logs"
    }
}

agent = agent llm {
    workflows: true  # Enables everything!

    # Optional: Custom Neo4j config
    workflows_uri: "bolt://localhost:7687"
    workflows_user: "neo4j"
    workflows_password: "password"

    model: gpt4
    tools: [file_tool, analysis_tool]
}
```

### 5.2 Manual Workflow Creation (Frontend)

```typescript
// Create workflow manually
const workflow = await createWorkflow({
  name: "Data Processing Pipeline",
  description: "Processes CSV files and generates reports",
  actions: [
    {
      sequence: 0,
      tool: "file_tool",
      action: "read_csv",
      inputs: { path: "input_file" },
      output: "csv_data"
    },
    {
      sequence: 1,
      tool: "analysis_tool",
      action: "analyze",
      inputs: { data: "csv_data" },
      output: "analysis_result"
    },
    {
      sequence: 2,
      tool: "report_tool",
      action: "generate_report",
      inputs: { analysis: "analysis_result", format: "pdf" },
      output: "report_file"
    }
  ]
});

// Create entrypoint
await createEntrypoint({
  workflowId: workflow.id,
  name: "process_data",
  description: "Process data files and generate reports",
  inputSchema: {
    type: "object",
    required: ["input_file"],
    properties: {
      input_file: { type: "string", description: "Path to input CSV file" }
    }
  }
});
```

### 5.3 API Execution

```bash
# Execute via entrypoint
curl -X POST http://localhost:8000/workflow/process_data \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "input_file": "/data/sales.csv"
    },
    "session_id": "user-123"
  }'

# Response
{
  "status": "success",
  "entrypoint": "process_data",
  "result": {
    "execution_id": "exec-456",
    "workflow_id": "w-789",
    "status": "completed",
    "final_outputs": {
      "csv_data": "...",
      "analysis_result": "...",
      "report_file": "/reports/sales_2024.pdf"
    }
  }
}
```

## 6. Future Extensions

### 6.1 Workflow Versioning
- Track workflow versions
- Allow rollback to previous versions
- A/B testing different workflow implementations

### 6.2 Execution History & Analytics
- Store workflow execution history in Neo4j
- Track success/failure rates
- Performance metrics per workflow
- Input/output caching for repeated executions

### 6.3 Conditional Logic
- Add conditional branching in workflows
- Support for parallel action execution
- Error handling and retry logic

### 6.4 Workflow Composition
- Nested workflows (workflows calling other workflows)
- Workflow templates with parameterization
- Import/export workflows as JSON

## 7. Success Criteria

✅ **Backend**:
- [ ] WorkflowExecutor executes action sequences correctly
- [ ] Workflows auto-captured during agent execution
- [ ] Top 3 similar workflows injected as context
- [ ] Workflows available as agent tools
- [ ] API entrypoints route to workflow execution
- [ ] All unit tests passing (>90% coverage)

✅ **Frontend**:
- [ ] View all workflows (auto-captured + manual)
- [ ] Create new workflows manually
- [ ] Edit existing workflows (auto + manual)
- [ ] Delete workflows
- [ ] Create entrypoints for workflows
- [ ] Execute workflows via GUI
- [ ] All frontend tests passing

✅ **Integration**:
- [ ] End-to-end: Agent captures workflow → Similar input → Workflow injected → Agent uses it
- [ ] End-to-end: Manual workflow → Entrypoint → API execution
- [ ] All integration tests passing

✅ **Documentation**:
- [ ] Configuration guide (.ww examples)
- [ ] API documentation
- [ ] Frontend usage guide
- [ ] Architecture diagrams

---

**End of Technical Design Document**
