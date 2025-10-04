import { useAgentMutation } from '@/lib/api';

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
  message?: string;
}

const FALLBACK_RESPONSE: WorkflowMatchResponse = {
  canUseWorkflow: false,
  message: "AI workflow matching not available",
};

/**
 * Hook to check if a task can be solved with an existing workflow
 * Sends task details to AI agent to determine workflow match
 */
export function useWorkflowMatch() {
  return useAgentMutation<WorkflowMatchResponse, WorkflowMatchRequest>(
    '/tasks/match-workflow',
    {
      method: 'POST',
      agentName: 'workflow-agent',
      onError: (error, variables) => {
        console.warn('Workflow match failed:', error.message);
        // Errors are handled gracefully by returning fallback in the component
      },
    }
  );
}
