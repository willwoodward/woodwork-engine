import { Plus } from "lucide-react";
import { useWorkflowsApi } from "@/hooks/useApiWithFallback";

type WorkflowSummary = {
  id: string;
  name: string;
};

interface WorkflowsListProps {
  selectedWorkflowId: string | null;
  onSelectWorkflow: (id: string | null) => void;
}

export default function WorkflowsList({ selectedWorkflowId, onSelectWorkflow }: WorkflowsListProps) {
  const { data, isLoading, error } = useWorkflowsApi();

  const handleCreateNew = () => {
    onSelectWorkflow("new");
  };

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading workflows...</p>;
  if (error) return <p className="text-sm text-destructive">Error loading workflows.</p>;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold">Workflows</h3>
        <button
          onClick={handleCreateNew}
          className="p-1 rounded hover:bg-accent"
          title="Create new workflow"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-auto">
        {(!data || data.length === 0) ? (
          <p className="text-sm text-muted-foreground">No workflows found.</p>
        ) : (
          <ul className="space-y-1">
            {data.map((workflow) => (
              <li
                key={workflow.id}
                onClick={() => onSelectWorkflow(workflow.id)}
                className={`cursor-pointer rounded-md p-2 text-sm transition-colors ${
                  selectedWorkflowId === workflow.id
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-accent"
                }`}
              >
                {workflow.name}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
