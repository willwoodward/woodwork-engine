import { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import WorkflowsList from "@/app/workflows/workflows-list";
import WorkflowBuilder from "@/app/workflows/workflow-builder";
import WorkflowDetailView from "@/components/workflows/workflow-detail-view";

export default function WorkflowsPage() {
  const location = useLocation();
  const navigate = useNavigate();

  // Get workflow ID from URL hash
  const workflowIdFromHash = (() => {
    const params = new URLSearchParams(location.hash.slice(1));
    return params.get('workflow');
  })();

  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(workflowIdFromHash);

  // Sync state with URL hash
  useEffect(() => {
    if (workflowIdFromHash !== selectedWorkflowId) {
      setSelectedWorkflowId(workflowIdFromHash);
    }
  }, [workflowIdFromHash]);

  // Update URL hash when selection changes
  const handleSelectWorkflow = (workflowId: string | null) => {
    setSelectedWorkflowId(workflowId);
    if (workflowId) {
      navigate(`#workflow=${workflowId}`);
    } else {
      navigate('#');
    }
  };

  // Determine if this is a new workflow or an existing stored workflow
  // const isNewWorkflow = selectedWorkflowId === "new";
  const isStoredWorkflow = selectedWorkflowId && selectedWorkflowId !== "new";

  return (
    <div className="flex h-full p-4 pt-0 gap-4">
      <div className="w-64 h-full bg-muted/50 rounded-xl p-4">
        <WorkflowsList
          selectedWorkflowId={selectedWorkflowId}
          onSelectWorkflow={handleSelectWorkflow}
        />
      </div>
      <div className="flex-1 h-full bg-muted/50 rounded-xl">
        {isStoredWorkflow ? (
          <WorkflowDetailView
            workflowId={selectedWorkflowId}
            onBack={() => handleSelectWorkflow(null)}
          />
        ) : (
          <WorkflowBuilder workflowId={selectedWorkflowId} />
        )}
      </div>
    </div>
  );
}
