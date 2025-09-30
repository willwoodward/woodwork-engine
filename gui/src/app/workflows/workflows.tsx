import { useState } from "react";
import WorkflowsList from "@/app/workflows/workflows-list";
import WorkflowBuilder from "@/app/workflows/workflow-builder";
import WorkflowDetailView from "@/components/workflows/workflow-detail-view";

export default function WorkflowsPage() {
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);

  // Determine if this is a new workflow or an existing stored workflow
  const isNewWorkflow = selectedWorkflowId === "new";
  const isStoredWorkflow = selectedWorkflowId && selectedWorkflowId !== "new";

  return (
    <div className="flex h-full p-4 pt-0 gap-4">
      <div className="w-64 h-full bg-muted/50 rounded-xl p-4">
        <WorkflowsList
          selectedWorkflowId={selectedWorkflowId}
          onSelectWorkflow={setSelectedWorkflowId}
        />
      </div>
      <div className="flex-1 h-full bg-muted/50 rounded-xl">
        {isStoredWorkflow ? (
          <WorkflowDetailView
            workflowId={selectedWorkflowId}
            onBack={() => setSelectedWorkflowId(null)}
          />
        ) : (
          <WorkflowBuilder workflowId={selectedWorkflowId} />
        )}
      </div>
    </div>
  );
}
