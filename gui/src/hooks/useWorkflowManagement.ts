import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api/client';

export interface WorkflowAction {
  sequence: number;
  tool: string;
  action: string;
  inputs: Record<string, any>;
  output: string;
}

export interface Workflow {
  id: string;
  name: string;
  description?: string;
  source?: 'auto' | 'manual';
  status?: string;
  created_at?: string;
  completed_at?: string;
  actions: WorkflowAction[];
}

export interface CreateWorkflowData {
  name: string;
  description?: string;
  actions: WorkflowAction[];
}

export interface UpdateWorkflowData {
  id: string;
  name?: string;
  description?: string;
  actions?: WorkflowAction[];
}

export interface CreateEntrypointData {
  workflowId: string;
  name: string;
  description: string;
  inputSchema: object;
}

export interface ExecuteWorkflowData {
  workflowId: string;
  inputs: Record<string, any>;
  sessionId?: string;
}

export function useWorkflowManagement() {
  const queryClient = useQueryClient();

  const createWorkflow = useMutation({
    mutationFn: async (data: CreateWorkflowData) => {
      return api.backend.post('/api/workflows', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });

  const updateWorkflow = useMutation({
    mutationFn: async (data: UpdateWorkflowData) => {
      const { id, ...updates } = data;
      return api.backend.put(`/api/workflows/${id}`, updates);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });

  const deleteWorkflow = useMutation({
    mutationFn: async (workflowId: string) => {
      return api.backend.delete(`/api/workflows/${workflowId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });

  const createEntrypoint = useMutation({
    mutationFn: async (data: CreateEntrypointData) => {
      const { workflowId, ...entrypoint } = data;
      return api.backend.post(`/api/workflows/${workflowId}/entrypoint`, entrypoint);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });

  const executeWorkflow = useMutation({
    mutationFn: async (data: ExecuteWorkflowData) => {
      const { workflowId, ...payload } = data;
      return api.backend.post(`/api/workflows/${workflowId}/execute`, payload);
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
