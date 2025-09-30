import { useQuery } from "@tanstack/react-query";
import { mockWorkflows } from "@/data/mock-data";

export interface WorkflowDetailGraph {
  nodes: Array<{
    id: string;
    type: "prompt" | "action";
    label: string;
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    type: "starts" | "next" | "depends_on";
  }>;
}

export interface WorkflowDetailMetadata {
  status: string;
  created_at: string;
  completed_at?: string;
  final_step?: number;
  prompt: string;
  total_actions: number;
}

export interface WorkflowDetailStep {
  id: string;
  name: string;
  tool: string;
  inputs: string;
  output: string;
  sequence: number;
  dependencies: Array<{
    id: string;
    tool: string;
    action: string;
    output: string;
  }>;
  description: string;
}

export interface WorkflowDetail {
  id: string;
  name: string;
  steps: WorkflowDetailStep[];
  metadata: WorkflowDetailMetadata;
  graph: WorkflowDetailGraph;
}

/**
 * Hook to fetch detailed workflow information including graph structure
 */
export function useWorkflowDetail(workflowId: string | null) {
  return useQuery<WorkflowDetail | null, Error>({
    queryKey: ["workflow-detail", workflowId],
    queryFn: async (): Promise<WorkflowDetail | null> => {
      if (!workflowId) return null;

      try {
        const response = await fetch(`/api/workflows/${workflowId}`);

        if (!response.ok) {
          if (response.status === 404) {
            // Try to find the workflow in mock data as fallback
            const mockWorkflow = mockWorkflows.find(w => w.id === workflowId);
            if (mockWorkflow && mockWorkflow.metadata && mockWorkflow.graph) {
              console.warn(`API returned 404, using mock data for workflow ${workflowId}`);
              return {
                id: mockWorkflow.id,
                name: mockWorkflow.name,
                steps: mockWorkflow.steps.map(step => ({
                  id: step.id || `step-${step.tool}-${step.name}`,
                  name: step.name,
                  tool: step.tool,
                  inputs: step.inputs || '{}',
                  output: step.output || 'unknown',
                  sequence: step.sequence || 0,
                  dependencies: step.dependencies || [],
                  description: step.description
                })),
                metadata: {
                  status: mockWorkflow.metadata.status || 'completed',
                  created_at: mockWorkflow.metadata.created_at || new Date().toISOString(),
                  completed_at: mockWorkflow.metadata.completed_at,
                  final_step: mockWorkflow.metadata.final_step || mockWorkflow.steps.length,
                  prompt: mockWorkflow.metadata.prompt || mockWorkflow.name,
                  total_actions: mockWorkflow.metadata.total_actions || mockWorkflow.steps.length
                },
                graph: mockWorkflow.graph
              } as WorkflowDetail;
            }
            return null;
          }
          throw new Error(`Failed to fetch workflow detail: ${response.status}`);
        }

        const data = await response.json();
        return data;
      } catch (error) {
        console.warn(`Failed to fetch workflow detail for ${workflowId}:`, error);

        // Fallback to mock data if API call fails completely
        const mockWorkflow = mockWorkflows.find(w => w.id === workflowId);
        if (mockWorkflow && mockWorkflow.metadata && mockWorkflow.graph) {
          console.warn(`Using mock data fallback for workflow ${workflowId}`);
          return {
            id: mockWorkflow.id,
            name: mockWorkflow.name,
            steps: mockWorkflow.steps.map(step => ({
              id: step.id || `step-${step.tool}-${step.name}`,
              name: step.name,
              tool: step.tool,
              inputs: step.inputs || '{}',
              output: step.output || 'unknown',
              sequence: step.sequence || 0,
              dependencies: step.dependencies || [],
              description: step.description
            })),
            metadata: {
              status: mockWorkflow.metadata.status || 'completed',
              created_at: mockWorkflow.metadata.created_at || new Date().toISOString(),
              completed_at: mockWorkflow.metadata.completed_at,
              final_step: mockWorkflow.metadata.final_step || mockWorkflow.steps.length,
              prompt: mockWorkflow.metadata.prompt || mockWorkflow.name,
              total_actions: mockWorkflow.metadata.total_actions || mockWorkflow.steps.length
            },
            graph: mockWorkflow.graph
          } as WorkflowDetail;
        }

        return null;
      }
    },
    enabled: !!workflowId,
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 1,
  });
}