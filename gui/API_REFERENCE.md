# GUI API Reference

Quick reference for frontend API endpoints and hooks.

## API Architecture

The system has **three servers**:
- **AI Agent** (port 8000) - Main Woodwork agent backend
- **GUI Server** (port 3000) - FastAPI server serving React app
- **Personal Server** (port 8001) - Optional personal data server

## API Clients

### Setup
```typescript
import { api } from '@/lib/api/client';
```

### Available Clients
- `api.backend.*` - Connects to port 8001 (personal server)
- `api.agent.*` - Connects to port 8000 (AI agent)

### HTTP Methods
```typescript
await api.backend.get<Type>('/endpoint');
await api.backend.post<Type>('/endpoint', body);
await api.backend.put<Type>('/endpoint', body);
await api.backend.delete<Type>('/endpoint');
await api.agent.get<Type>('/endpoint');
```

## React Query Hooks

### Workflows
```typescript
import { useWorkflows, useWorkflowDetail } from '@/hooks/useEnhancedAPI';

// Get workflows list
const { data, isLoading, refetch } = useWorkflows({
  status?: string,
  category?: string,
  search?: string,
  limit?: number
});
// Returns: { workflows: Workflow[], total: number, categories: string[] }

// Get workflow detail
const { data: workflow } = useWorkflowDetail(workflowId);
// Returns: WorkflowDetail with steps, metadata, graph
```

### Agents
```typescript
import { useAgents } from '@/hooks/useEnhancedAPI';

const { data } = useAgents();
// Returns: { agents: Agent[], capabilities: string[], apiInputs: any[] }
```

### Chat
```typescript
import { useChatAPI } from '@/hooks/useChatAPI';

const { messages, sendMessage, isConnected } = useChatAPI();

// Send message
sendMessage.mutate({ message: "Hello", request_id?: string });
```

## GUI Server Endpoints

All served from `localhost:3000` (relative paths in frontend):

### Workflows
- `GET /api/workflows` - List workflows with filters
  - Query params: `status`, `category`, `search`, `limit`
- `GET /api/workflows/get` - Get stored workflows (legacy)
- `GET /api/workflows/{id}` - Get workflow detail with graph
- `POST /api/workflows/trigger` - Trigger workflow execution
- `POST /api/workflows/match` - Match workflow to input

### Agents
- `GET /api/agents` - List available agents

### Chat/Input
- `POST /api/input` - Send user input
  - Body: `{ input: string, request_id?: string, session_id?: string }`
- `GET /api/input` - Get input status

### Inbox
- `GET /api/inbox/requests` - Get pending human input requests
- `POST /api/inbox/respond` - Respond to inbox request

### WebSocket
- `WS /ws` - Real-time events (agent thoughts, actions, errors)

## AI Agent Endpoints

Served from `localhost:8000`:

### Workflows (Neo4j-backed)
- `GET /api/workflows` - Query workflows from Neo4j
  - Query params: `status`, `limit`
  - Returns workflows with actions from graph database

### Agents
- `GET /api/agents` - List configured agents

## Type Definitions

```typescript
import type { Workflow, Agent, WorkflowDetail } from '@/types/api-types';

interface Workflow {
  id: string;
  name: string;
  status?: 'completed' | 'in_progress' | 'failed';
  source?: 'auto' | 'manual';
  actions?: Action[];
  metadata?: Record<string, any>;
  created_at?: string;
  completed_at?: string;
}

interface Agent {
  id: string;
  name: string;
  capabilities: string[];
  status: 'online' | 'offline';
}
```

## Common Patterns

### Fetch and auto-refresh
```typescript
const { data, refetch } = useWorkflows({ limit: 50 });

useEffect(() => {
  const interval = setInterval(() => refetch(), 2000);
  return () => clearInterval(interval);
}, [refetch]);
```

### Direct fetch (when hooks not suitable)
```typescript
const response = await fetch('/api/workflows');
const data = await response.json();
```

### WebSocket events
```typescript
// WebSocket automatically connects in useChatAPI hook
// Events: agent.thought, agent.action, tool.call, tool.observation, etc.
```

## Configuration

API URLs configured in:
- `gui/src/lib/api/config.ts`
- Environment variables: `VITE_BACKEND_URL`, `VITE_AGENT_URL`

Default ports:
- GUI Server: 3000
- AI Agent: 8000
- Personal Server: 8001
