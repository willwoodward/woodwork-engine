import { useBackendMutation } from '@/lib/api';
import type { WorkflowGraphData } from '@/components/workflows/workflow-graph';

export interface WorkflowMatchRequest {
  taskTitle: string;
  taskDescription?: string;
  tags?: string[];
}

export interface WorkflowMatchResponse {
  canUseWorkflow: boolean;
  workflowId?: string;
  workflowName?: string;
  confidence?: number;
  actions?: Array<{
    id: string;
    name: string;
    description: string;
  }>;
  graph?: WorkflowGraphData;
  message?: string;
}

/**
 * Hook to check if a task can be solved with an existing workflow
 * Sends task details to personal server which provides mock workflow matches
 *
 * Gracefully handles server being down - task will be added manually
 */
export function useWorkflowMatch() {
  return useBackendMutation<WorkflowMatchResponse, WorkflowMatchRequest>(
    '/tasks/match-workflow',
    {
      method: 'POST',
      retry: false, // Don't retry - fail fast if server is down
      onError: (error) => {
        // Silently handle server connection errors
        // The component will fall back to manual task creation
        if (error.message.includes('Failed to fetch') ||
            error.message.includes('ERR_CONNECTION_REFUSED')) {
          // Server is down - this is expected and okay
          return;
        }
        // Only log unexpected errors
        console.warn('Workflow match error:', error.message);
      },
    }
  );
}
