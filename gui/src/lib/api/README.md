# API Abstraction Layer

A unified, type-safe API client for communicating with backend services and AI agents.

## Features

- ✅ **Dual API Support**: Backend web API + AI Agent APIs
- ✅ **Multi-Host Agents**: Connect to agents on different IPs/ports
- ✅ **Cross-Session**: Communicate with agents across sessions
- ✅ **React Query Integration**: Built-in caching, loading states, and error handling
- ✅ **Automatic Fallback**: Graceful degradation with mock data
- ✅ **Type-Safe**: Full TypeScript support
- ✅ **Flexible Configuration**: Runtime configuration updates

## Quick Start

### Backend API

```typescript
import { useBackendQuery, useBackendMutation } from '@/lib/api';

// GET request with fallback
function TaskList() {
  const { data: tasks, isLoading } = useBackendQuery('/tasks', {
    fallbackData: mockTasks,
  });

  return <div>{tasks.map(task => ...)}</div>;
}

// POST request
function CreateTask() {
  const createTask = useBackendMutation('/tasks', {
    method: 'POST',
    onSuccess: (data) => console.log('Task created:', data),
  });

  return (
    <button onClick={() => createTask.mutate({ title: 'New task' })}>
      Create
    </button>
  );
}
```

### AI Agent API

```typescript
import { useAgentQuery, useAgentMutation } from '@/lib/api';

// Query an agent
function AgentStatus() {
  const { data: status } = useAgentQuery('/status', {
    agentName: 'workflow-agent',
    sessionId: 'session-123',
  });

  return <div>Agent status: {status.state}</div>;
}

// Execute workflow on agent
function ExecuteWorkflow() {
  const execute = useAgentMutation('/execute', {
    agentName: 'workflow-agent',
    onSuccess: (result) => console.log('Workflow result:', result),
  });

  return (
    <button onClick={() => execute.mutate({ workflowId: 'abc123' })}>
      Execute Workflow
    </button>
  );
}
```

### Multi-Agent Queries

```typescript
import { useMultiAgentQuery } from '@/lib/api';

function AgentCluster() {
  const { data, isLoading } = useMultiAgentQuery(
    '/health',
    ['agent-1', 'agent-2', 'agent-3']
  );

  // data is an array of responses from all agents
  return <div>{data.length} agents healthy</div>;
}
```

### Cross-Session Communication

```typescript
import { useCrossSessionAgent } from '@/lib/api';

function CrossSessionView() {
  const { data } = useCrossSessionAgent(
    '/tasks',
    'other-session-id',
    {
      agentName: 'shared-agent',
    }
  );

  return <div>Tasks from other session: {data?.length}</div>;
}
```

## Configuration

### Default Configuration

```typescript
// Configured via environment variables
VITE_BACKEND_URL=http://localhost:8000
VITE_AGENT_URL=http://localhost:5000
VITE_AGENT_WS_URL=ws://localhost:5000
```

### Runtime Configuration

```typescript
import { setAgentEndpoint, updateApiConfig } from '@/lib/api';

// Add a new agent dynamically
setAgentEndpoint('remote-agent', {
  baseUrl: 'http://192.168.1.100:5000',
  wsUrl: 'ws://192.168.1.100:5000',
  agentId: 'agent-remote-1',
  sessionId: 'session-xyz',
  timeout: 120000,
});

// Update entire config
updateApiConfig({
  backend: {
    baseUrl: 'https://api.production.com',
  },
});
```

### Low-Level API Client

For more control, use the raw API client:

```typescript
import { api } from '@/lib/api';

// Backend requests
const response = await api.backend.get('/tasks');
const created = await api.backend.post('/tasks', { title: 'New task' });

// Agent requests
const status = await api.agent.get('/status', {
  agentName: 'workflow-agent',
  sessionId: 'session-123',
});

const result = await api.agent.post('/execute', {
  workflowId: 'abc123',
}, {
  agentName: 'workflow-agent',
  agentId: 'agent-1',
});
```

## Advanced Examples

### With TypeScript

```typescript
interface Task {
  id: string;
  title: string;
  completed: boolean;
}

interface WorkflowResult {
  success: boolean;
  steps: string[];
}

// Type-safe queries
const { data } = useBackendQuery<Task[]>('/tasks');
const workflow = useAgentMutation<WorkflowResult, { workflowId: string }>('/execute');
```

### Error Handling

```typescript
const { data, error, isError } = useBackendQuery('/tasks', {
  onError: (error) => {
    console.error('Failed to fetch tasks:', error.message);
    // error.status - HTTP status code
    // error.request - Original request details
  },
});

if (isError) {
  return <div>Error: {error.message}</div>;
}
```

### Custom Query Keys

```typescript
const { data } = useBackendQuery('/tasks', {
  queryKey: ['tasks', 'user', userId],
  enabled: !!userId, // Only run when userId exists
  staleTime: 10000, // Consider data fresh for 10 seconds
});
```

## Architecture

```
┌─────────────────────────────────────────────┐
│           React Components                   │
└─────────────────┬───────────────────────────┘
                  │
    ┌─────────────┴──────────────┐
    │                            │
┌───▼────────────┐    ┌─────────▼──────────┐
│ useBackendQuery│    │  useAgentQuery     │
│useBackendMutation   │ useAgentMutation   │
└───┬────────────┘    └─────────┬──────────┘
    │                           │
    └─────────┬─────────────────┘
              │
        ┌─────▼──────┐
        │ ApiClient  │
        └─────┬──────┘
              │
    ┌─────────┴──────────┐
    │                    │
┌───▼────────┐    ┌─────▼──────────┐
│ Backend API│    │  Agent APIs    │
│ (Single)   │    │ (Multi-Host)   │
└────────────┘    └────────────────┘
```

## Migration Guide

### From useApiWithFallback

```typescript
// Old
const { data } = useApiWithFallback({
  queryKey: ['tasks'],
  endpoint: '/api/tasks',
  fallbackData: mockTasks,
});

// New
const { data } = useBackendQuery('/api/tasks', {
  queryKey: ['tasks'],
  fallbackData: mockTasks,
});
```

### From fetch

```typescript
// Old
const response = await fetch('/api/tasks');
const data = await response.json();

// New
const { data } = await api.backend.get('/api/tasks');
```
