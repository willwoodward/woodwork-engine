# API Usage Examples

Real-world examples of using the API abstraction layer.

## Scenario 1: Task Management with Backend API

```typescript
// hooks/useTaskOperations.ts
import { useBackendQuery, useBackendMutation } from '@/lib/api';
import type { Task } from '@/types/task';

export function useTaskOperations() {
  // Fetch all tasks
  const { data: tasks, isLoading, refetch } = useBackendQuery<Task[]>('/tasks', {
    fallbackData: mockTasks,
    staleTime: 60000, // 1 minute
  });

  // Create task
  const createTask = useBackendMutation<Task, Partial<Task>>('/tasks', {
    method: 'POST',
    onSuccess: () => refetch(),
  });

  // Update task
  const updateTask = useBackendMutation<Task, Partial<Task>>('/tasks/:id', {
    method: 'PATCH',
    onSuccess: () => refetch(),
  });

  // Delete task
  const deleteTask = useBackendMutation<void, string>('/tasks/:id', {
    method: 'DELETE',
    onSuccess: () => refetch(),
  });

  return {
    tasks,
    isLoading,
    createTask: (task: Partial<Task>) => createTask.mutate(task),
    updateTask: (id: string, updates: Partial<Task>) =>
      updateTask.mutate({ id, ...updates }),
    deleteTask: (id: string) => deleteTask.mutate(id),
  };
}
```

## Scenario 2: Workflow Execution on AI Agent

```typescript
// hooks/useWorkflowExecution.ts
import { useAgentMutation, useAgentQuery } from '@/lib/api';

interface ExecuteWorkflowRequest {
  workflowId: string;
  taskTitle: string;
  context?: Record<string, any>;
}

interface WorkflowStatus {
  status: 'pending' | 'running' | 'completed' | 'failed';
  currentStep: number;
  totalSteps: number;
  result?: any;
  error?: string;
}

export function useWorkflowExecution(sessionId: string) {
  // Execute workflow on agent
  const execute = useAgentMutation<WorkflowStatus, ExecuteWorkflowRequest>(
    '/workflows/execute',
    {
      agentName: 'workflow-agent',
      onSuccess: (data) => {
        console.log('Workflow started:', data);
      },
    }
  );

  // Poll for status
  const { data: status, refetch } = useAgentQuery<WorkflowStatus>(
    '/workflows/status',
    {
      agentName: 'workflow-agent',
      sessionId,
      enabled: false, // Manual polling
    }
  );

  return {
    execute: (request: ExecuteWorkflowRequest) => execute.mutate(request),
    status,
    pollStatus: refetch,
    isExecuting: execute.isPending,
  };
}

// Usage in component
function WorkflowExecutor() {
  const { execute, status, pollStatus } = useWorkflowExecution('session-123');

  useEffect(() => {
    if (status?.status === 'running') {
      const interval = setInterval(pollStatus, 2000);
      return () => clearInterval(interval);
    }
  }, [status?.status]);

  return (
    <button onClick={() => execute({ workflowId: 'abc', taskTitle: 'Fix bug' })}>
      Execute Workflow
    </button>
  );
}
```

## Scenario 3: Multi-Agent Coordination

```typescript
// hooks/useAgentCluster.ts
import { useMultiAgentQuery, setAgentEndpoint } from '@/lib/api';

// Setup agent cluster
export function setupAgentCluster() {
  setAgentEndpoint('agent-1', {
    baseUrl: 'http://localhost:5001',
    agentId: 'agent-1',
  });

  setAgentEndpoint('agent-2', {
    baseUrl: 'http://192.168.1.100:5000',
    agentId: 'agent-2',
  });

  setAgentEndpoint('agent-3', {
    baseUrl: 'http://192.168.1.101:5000',
    agentId: 'agent-3',
  });
}

export function useAgentCluster() {
  const { data, isLoading, errors } = useMultiAgentQuery(
    '/health',
    ['agent-1', 'agent-2', 'agent-3']
  );

  const healthyAgents = data.filter((d) => d.status === 'healthy');

  return {
    agents: data,
    healthyCount: healthyAgents.length,
    totalCount: 3,
    isLoading,
    hasErrors: errors.length > 0,
  };
}

// Usage
function AgentClusterDashboard() {
  const { healthyCount, totalCount, agents } = useAgentCluster();

  return (
    <div>
      <h2>{healthyCount} / {totalCount} agents healthy</h2>
      {agents.map((agent, i) => (
        <div key={i}>{agent.agentId}: {agent.status}</div>
      ))}
    </div>
  );
}
```

## Scenario 4: Cross-Session Agent Communication

```typescript
// hooks/useCrossSessionTasks.ts
import { useCrossSessionAgent } from '@/lib/api';
import type { Task } from '@/types/task';

export function useCrossSessionTasks(otherSessionId: string) {
  const { data: tasks, isLoading } = useCrossSessionAgent<Task[]>(
    '/tasks',
    otherSessionId,
    {
      agentName: 'shared-agent',
      enabled: !!otherSessionId,
    }
  );

  return {
    tasks: tasks || [],
    isLoading,
  };
}

// Usage: View another user's tasks
function SharedTaskView({ sessionId }: { sessionId: string }) {
  const { tasks, isLoading } = useCrossSessionTasks(sessionId);

  if (isLoading) return <div>Loading...</div>;

  return (
    <div>
      <h3>Tasks from session {sessionId}</h3>
      {tasks.map((task) => (
        <div key={task.id}>{task.title}</div>
      ))}
    </div>
  );
}
```

## Scenario 5: Dynamic Agent Discovery

```typescript
// hooks/useAgentDiscovery.ts
import { setAgentEndpoint, useAgentQuery } from '@/lib/api';

interface AgentInfo {
  id: string;
  name: string;
  host: string;
  port: number;
  capabilities: string[];
}

export function useAgentDiscovery() {
  // Query discovery service on backend
  const { data: agents, refetch } = useBackendQuery<AgentInfo[]>(
    '/agents/discover',
    {
      staleTime: 30000, // Refresh every 30 seconds
    }
  );

  // Register discovered agents
  useEffect(() => {
    if (agents) {
      agents.forEach((agent) => {
        setAgentEndpoint(agent.name, {
          baseUrl: `http://${agent.host}:${agent.port}`,
          agentId: agent.id,
        });
      });
    }
  }, [agents]);

  return {
    agents: agents || [],
    refresh: refetch,
  };
}

// Usage
function AgentDiscoveryPanel() {
  const { agents, refresh } = useAgentDiscovery();

  return (
    <div>
      <button onClick={refresh}>Refresh Agents</button>
      <ul>
        {agents.map((agent) => (
          <li key={agent.id}>
            {agent.name} @ {agent.host}:{agent.port}
            <br />
            Capabilities: {agent.capabilities.join(', ')}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

## Scenario 6: Fallback Chain

```typescript
// Try agent first, fall back to backend, then mock data
import { useAgentQuery, useBackendQuery } from '@/lib/api';

export function useRobustDataFetch() {
  const agentQuery = useAgentQuery('/data', {
    retry: 0, // Don't retry agent
  });

  const backendQuery = useBackendQuery('/data', {
    enabled: agentQuery.isError, // Only if agent fails
    fallbackData: mockData,
  });

  return {
    data: agentQuery.data || backendQuery.data,
    source: agentQuery.data ? 'agent' : backendQuery.data ? 'backend' : 'mock',
    isLoading: agentQuery.isLoading || backendQuery.isLoading,
  };
}
```

## Scenario 7: Real-Time Updates with Polling

```typescript
// hooks/useRealtimeAgentStatus.ts
import { useAgentQuery } from '@/lib/api';
import { useEffect } from 'react';

export function useRealtimeAgentStatus(agentName: string, interval = 5000) {
  const { data, refetch } = useAgentQuery('/status', {
    agentName,
    staleTime: 0, // Always fetch fresh
  });

  useEffect(() => {
    const timer = setInterval(refetch, interval);
    return () => clearInterval(timer);
  }, [refetch, interval]);

  return data;
}

// Usage
function AgentMonitor() {
  const status = useRealtimeAgentStatus('workflow-agent', 3000);

  return (
    <div>
      Agent Status: {status?.state}
      <br />
      Last Updated: {new Date().toLocaleTimeString()}
    </div>
  );
}
```

## Scenario 8: Optimistic Updates

```typescript
// hooks/useOptimisticTasks.ts
import { useBackendQuery, useBackendMutation } from '@/lib/api';
import { useQueryClient } from '@tanstack/react-query';

export function useOptimisticTasks() {
  const queryClient = useQueryClient();
  const { data: tasks } = useBackendQuery<Task[]>('/tasks');

  const createTask = useBackendMutation<Task, Partial<Task>>('/tasks', {
    method: 'POST',
    onMutate: async (newTask) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['backend', '/tasks'] });

      // Snapshot previous value
      const previous = queryClient.getQueryData(['backend', '/tasks']);

      // Optimistically update
      queryClient.setQueryData(['backend', '/tasks'], (old: Task[]) => [
        ...old,
        { ...newTask, id: 'temp-id', completed: false },
      ]);

      return { previous };
    },
    onError: (err, newTask, context) => {
      // Rollback on error
      queryClient.setQueryData(['backend', '/tasks'], context?.previous);
    },
    onSettled: () => {
      // Refetch after mutation
      queryClient.invalidateQueries({ queryKey: ['backend', '/tasks'] });
    },
  });

  return {
    tasks: tasks || [],
    createTask: (task: Partial<Task>) => createTask.mutate(task),
  };
}
```
