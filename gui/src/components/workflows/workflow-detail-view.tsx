"use client";

import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import type { Node } from "@xyflow/react";
import { Calendar, ArrowRight } from "lucide-react";
import { useWorkflowDetail } from "@/hooks/useWorkflowDetail";
import { SidebarSection, InfoDisplay, EmptyState } from "@/components/ui";
import { WorkflowGraph } from "./workflow-graph";

interface WorkflowDetailViewProps {
  workflowId?: string;
  onBack?: () => void;
}

// Wrapper component for use with React Router
export function WorkflowDetailView() {
  const { workflowId } = useParams<{ workflowId: string }>();
  const navigate = useNavigate();

  if (!workflowId) {
    return <EmptyState message="No workflow ID provided" />;
  }

  return <WorkflowDetailViewInner workflowId={workflowId} onBack={() => navigate('/workflow-browser')} />;
}

function WorkflowDetailViewInner({ workflowId, onBack }: Required<WorkflowDetailViewProps>) {
  const { data: workflow, isLoading, error } = useWorkflowDetail(workflowId);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return "Unknown";
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  if (isLoading) {
    return <div className="flex items-center justify-center h-64">
      <div className="text-muted-foreground">Loading workflow details...</div>
    </div>;
  }

  if (error || !workflow) {
    return <div className="flex items-center justify-center h-64">
      <EmptyState message="Workflow not found or failed to load" />
    </div>;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b bg-card">
        <div className="flex items-center gap-3 mb-2">
          {onBack && (
            <button
              onClick={onBack}
              className="text-muted-foreground hover:text-foreground"
            >
              ← Back
            </button>
          )}
          <h2 className="text-xl font-semibold">{workflow.name}</h2>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="bg-green-500/20 text-green-600 dark:text-green-400 px-2 py-1 rounded text-xs border border-green-500/30">
              {workflow.metadata.status}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-6 text-sm text-muted-foreground">
          <div className="flex items-center gap-1">
            <Calendar className="w-4 h-4" />
            <span>Completed: {formatDate(workflow.metadata.completed_at)}</span>
          </div>
          <div className="flex items-center gap-1">
            <ArrowRight className="w-4 h-4" />
            <span>{workflow.metadata.total_actions} actions</span>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex flex-1 gap-4 p-4">
        {/* Graph view */}
        <div className="flex-1 rounded-xl bg-muted/50 p-2">
          {workflow?.graph && (
            <WorkflowGraph
              graph={workflow.graph}
              onNodeClick={setSelectedNode}
              className="w-full h-full"
            />
          )}
        </div>

        {/* Sidebar */}
        <aside className="w-80 rounded-xl bg-muted/30 p-4 space-y-4">
          <SidebarSection title="Workflow Information">
            <InfoDisplay
              items={[
                { key: "Status", value: workflow.metadata.status },
                { key: "Created", value: formatDate(workflow.metadata.created_at) },
                { key: "Completed", value: formatDate(workflow.metadata.completed_at) },
                { key: "Total Steps", value: workflow.metadata.total_actions.toString() },
              ]}
            />
          </SidebarSection>

          <SidebarSection title="Original Prompt">
            <p className="text-sm text-muted-foreground p-2 bg-muted rounded">
              {workflow.metadata.prompt}
            </p>
          </SidebarSection>

          {selectedNode && (
            <SidebarSection title="Selected Node">
              <InfoDisplay
                items={[
                  { key: "Type", value: String(selectedNode.data.type) },
                  { key: "ID", value: selectedNode.id },
                  ...(selectedNode.data.tool ? [{ key: "Tool", value: String(selectedNode.data.tool) }] : []),
                  ...(selectedNode.data.action ? [{ key: "Action", value: String(selectedNode.data.action) }] : []),
                ]}
              />
            </SidebarSection>
          )}

          <SidebarSection title="Legend">
            <div className="space-y-2 text-xs">
              {/* Node Types */}
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-blue-500/20 rounded border border-blue-500/30"></div>
                <span>Input/Prompt</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-500/20 rounded border border-green-500/30"></div>
                <span>Action/Step</span>
              </div>

              {/* Edge Types */}
              <div className="mt-3 pt-2 border-t border-border">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-0.5" style={{ backgroundColor: '#3b82f6' }}></div>
                  <span>Starts</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-0.5" style={{ backgroundColor: '#10b981' }}></div>
                  <span>Next Step</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-0.5 border-dashed border-t-2" style={{ borderColor: '#ffffff' }}></div>
                  <span>Dependency</span>
                </div>
              </div>
            </div>
          </SidebarSection>
        </aside>
      </div>
    </div>
  );
}

// Also export as default for backwards compatibility
export default WorkflowDetailViewInner;