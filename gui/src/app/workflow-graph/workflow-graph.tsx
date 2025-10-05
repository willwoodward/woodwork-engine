"use client"

import { useState, useEffect, useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ForceGraph } from "@/components/graphs/ForceGraph";
import type { GraphData } from "@/components/graphs/ForceGraph";
import {
  SidebarSection,
  InfoDisplay,
  EmptyState,
  WorkflowCard,
} from "@/components/ui";
import { useWorkflows } from "@/hooks/useEnhancedAPI";

export default function WorkflowGraphPage() {
  const location = useLocation();
  const navigate = useNavigate();

  // Fetch workflows from Neo4j with auto-refresh every 2 seconds for real-time updates
  const { data: workflowData, isLoading, refetch } = useWorkflows({
    limit: 50
  });

  const workflows = workflowData?.workflows || [];

  // Get highlighted workflow ID from URL hash
  const highlightedWorkflowId = useMemo(() => {
    const params = new URLSearchParams(location.hash.slice(1));
    return params.get('workflow');
  }, [location.hash]);

  // Auto-refresh every 2 seconds to show real-time workflow updates
  useEffect(() => {
    const interval = setInterval(() => {
      refetch();
    }, 2000); // Fast refresh - graph only adds new nodes, doesn't reset
    return () => clearInterval(interval);
  }, [refetch]);

  // Transform workflow data into force graph format
  const graphData = useMemo<GraphData>(() => {
    const nodes: GraphData['nodes'] = [];
    const links: GraphData['links'] = [];
    const agentNodes = new Map<string, boolean>(); // Track which agent nodes we've added

    workflows.forEach((wf) => {
      const actions = wf.actions || [];
      const agentId = wf.metadata?.component_id || wf.metadata?.session_id || 'default-agent';

      // Add agent node if we haven't already
      if (!agentNodes.has(agentId)) {
        nodes.push({
          id: `agent-${agentId}`,
          label: agentId.replace(/_/g, ' ').slice(0, 20),
          type: 'agent',
          group: agentId,
          size: 10,
          metadata: { agentId },
        });
        agentNodes.set(agentId, true);
      }

      // Add prompt/workflow node
      const promptNodeId = `${wf.id}-prompt`;
      nodes.push({
        id: promptNodeId,
        label: wf.name?.slice(0, 30) || 'Workflow',
        type: 'prompt',
        group: wf.id,
        size: 8,
        metadata: { workflowId: wf.id, workflow: wf, agentId },
      });

      // Link workflow to agent
      links.push({
        source: `agent-${agentId}`,
        target: promptNodeId,
        type: 'executes',
        label: 'executes',
      });

      // Add action nodes
      actions.forEach((action, index) => {
        const actionNodeId = `${wf.id}-action-${index}`;
        nodes.push({
          id: actionNodeId,
          label: action.action?.slice(0, 20) || action.tool || `Action ${index + 1}`,
          type: 'action',
          group: wf.id,
          size: 5,
          metadata: {
            workflowId: wf.id,
            action,
            tool: action.tool,
          },
        });

        // Link from prompt to first action
        if (index === 0) {
          links.push({
            source: promptNodeId,
            target: actionNodeId,
            type: 'starts',
            label: 'starts',
          });
        }

        // Link to next action
        if (index > 0) {
          const prevActionNodeId = `${wf.id}-action-${index - 1}`;
          links.push({
            source: prevActionNodeId,
            target: actionNodeId,
            type: 'next',
            label: 'next',
          });
        }
      });
    });

    return { nodes, links };
  }, [workflows]);

  const [selectedNode, setSelectedNode] = useState<any>(null);

  // Find selected workflow when node is clicked
  const selectedWorkflow = useMemo(() => {
    if (!selectedNode?.metadata?.workflowId) return null;
    return workflows.find(wf => wf.id === selectedNode.metadata.workflowId);
  }, [selectedNode, workflows]);

  const handleNodeClick = (node: any) => {
    setSelectedNode(node);
    if (node.metadata?.workflowId) {
      navigate(`#workflow=${node.metadata.workflowId}`);
    }
  };

  return (
    <div className="flex flex-1 gap-4 p-4 pt-0 h-full">
      {/* Force Graph View */}
      <div className="flex-1 rounded-xl bg-muted/50 p-4 flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">Real-time Workflow Graph</h3>
          {isLoading && (
            <span className="text-xs text-muted-foreground animate-pulse">
              Updating...
            </span>
          )}
          <span className="text-xs text-muted-foreground">
            {workflows.length} workflow{workflows.length !== 1 ? 's' : ''} • {graphData.nodes.length} nodes
          </span>
        </div>

        <div className="flex-1 relative">
          {graphData.nodes.length === 0 ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <EmptyState message="No workflows found. Start a task to see workflows appear in real-time!" />
            </div>
          ) : (
            <ForceGraph
              data={graphData}
              onNodeClick={handleNodeClick}
              highlightedNodeId={highlightedWorkflowId || selectedNode?.id}
              className="w-full h-full"
            />
          )}
        </div>
      </div>

      {/* Sidebar */}
      <aside className="w-80 rounded-xl bg-muted/30 p-4 space-y-4 overflow-auto">
        {selectedNode ? (
          <>
            <SidebarSection title="Selected Node">
              <InfoDisplay
                items={[
                  { key: "Type", value: selectedNode.type },
                  { key: "Label", value: selectedNode.label },
                  ...(selectedNode.metadata?.tool ? [{ key: "Tool", value: selectedNode.metadata.tool }] : []),
                ]}
              />
            </SidebarSection>

            {selectedWorkflow && (
              <SidebarSection title="Workflow Details">
                <InfoDisplay
                  items={[
                    { key: "Name", value: selectedWorkflow.name || 'Unknown' },
                    { key: "Status", value: selectedWorkflow.status || 'unknown' },
                    { key: "Actions", value: (selectedWorkflow.actions?.length || 0).toString() },
                    ...(selectedWorkflow.created_at ? [{ key: "Created", value: new Date(selectedWorkflow.created_at).toLocaleString() }] : []),
                  ]}
                />
              </SidebarSection>
            )}
          </>
        ) : (
          <EmptyState message="Click a node to view details" />
        )}

        <SidebarSection title="Recent Workflows">
          <div className="space-y-2 max-h-96 overflow-auto">
            {workflows.length === 0 && (
              <EmptyState message="No workflows found" />
            )}
            {workflows.slice(0, 10).map((wf) => (
              <div
                key={wf.id}
                onClick={() => {
                  navigate(`#workflow=${wf.id}`);
                  // Find and select the prompt node for this workflow
                  const promptNode = graphData.nodes.find(n => n.id === `${wf.id}-prompt`);
                  if (promptNode) setSelectedNode(promptNode);
                }}
                className="cursor-pointer"
              >
                <WorkflowCard
                  id={wf.id}
                  name={wf.name}
                  stepCount={(wf.actions || []).length}
                  metadata={wf.metadata}
                />
              </div>
            ))}
          </div>
        </SidebarSection>

        <SidebarSection title="Legend">
          <div className="space-y-2 text-xs">
            {/* Node Types */}
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-orange-500/20 rounded border border-orange-500/30"></div>
              <span>Agent</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-blue-500/20 rounded border border-blue-500/30"></div>
              <span>Workflow/Prompt</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-green-500/20 rounded border border-green-500/30"></div>
              <span>Action/Step</span>
            </div>

            {/* Edge Types */}
            <div className="mt-3 pt-2 border-t border-border">
              <div className="flex items-center gap-2">
                <div className="w-4 h-0.5" style={{ backgroundColor: '#f59e0b' }}></div>
                <span>Executes</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-0.5" style={{ backgroundColor: '#3b82f6' }}></div>
                <span>Starts</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-0.5" style={{ backgroundColor: '#10b981' }}></div>
                <span>Next Step</span>
              </div>
            </div>
          </div>
        </SidebarSection>
      </aside>
    </div>
  );
}
