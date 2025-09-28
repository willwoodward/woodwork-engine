import { useWorkflowsApi } from "./useApiWithFallback";

// Legacy type compatibility - map to new types
export type WorkflowStep = {
  id?: string;
  name?: string;
  tool?: string;
  input?: Record<string, unknown> | null;
};

export type Workflow = {
  id: string;
  name?: string;
  steps?: WorkflowStep[];
};

export function useWorkflows() {
  const result = useWorkflowsApi();

  // Transform the data to match the legacy interface
  return {
    ...result,
    data: result.data?.map(workflow => ({
      id: workflow.id,
      name: workflow.name,
      steps: workflow.steps.map((step, index) => ({
        id: `${workflow.id}-${index}`,
        name: step.name,
        tool: step.tool,
        input: null,
      })),
    })) || [],
  };
}
