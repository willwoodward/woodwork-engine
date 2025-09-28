import React, { useState } from "react";
import WorkflowsList from "@/app/workflows/workflows-list";
import WorkflowBuilder from "@/app/workflows/workflow-builder";

export default function WorkflowsPage() {
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);

  return (
    <div className="flex h-full p-4 pt-0 gap-4">
      <div className="w-64 h-full bg-muted/50 rounded-xl p-4">
        <WorkflowsList
          selectedWorkflowId={selectedWorkflowId}
          onSelectWorkflow={setSelectedWorkflowId}
        />
      </div>
      <div className="flex-1 h-full bg-muted/50 rounded-xl">
        <WorkflowBuilder workflowId={selectedWorkflowId} />
      </div>
    </div>
  );
}
