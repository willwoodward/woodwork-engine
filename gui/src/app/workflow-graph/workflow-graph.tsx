"use client"

import { useCallback, useMemo, useState } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
} from "@xyflow/react";
import type {
  Node,
  Edge,
  Connection,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  SidebarSection,
  InfoDisplay,
  EmptyState,
  WorkflowCard,
  ToolIcon,
} from "@/components/ui";
import { useWorkflowsApi } from "@/hooks/useApiWithFallback";

// Define node data types
type NodeData = {
  label: string;
  step?: {
    name?: string;
    tool?: string;
    description?: string;
  };
  workflow?: {
    name?: string;
  };
};

// Custom node component with icon
const CustomNode = ({ data }: { data: NodeData }) => {
  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-card text-card-foreground border-2 border-border rounded-lg shadow-sm min-w-[180px]">
      <ToolIcon tool={data.step?.tool || ''} className="w-4 h-4 text-muted-foreground flex-shrink-0" />
      <span className="text-sm font-medium">{data.label}</span>
    </div>
  );
};

const nodeTypes = {
  custom: CustomNode,
};

export default function WorkflowGraphPage() {
  const { data: workflows = [], isLoading } = useWorkflowsApi();

  const initialData = useMemo(() => {
    const nodes: Node[] = [];
    const edges: Edge[] = [];

    workflows.forEach((wf, wfIndex) => {
      const steps = wf.steps || [];

      steps.forEach((step, stepIndex) => {
        const id = `${wf.id}-${stepIndex}`;
        nodes.push({
          id,
          type: 'custom',
          position: { x: 200 * stepIndex + wfIndex * 30, y: wfIndex * 200 + 50 },
          data: {
            label: step.name || step.tool || `Step ${stepIndex + 1}`,
            step,
            workflow: wf,
          },
        });

        if (stepIndex > 0) {
          edges.push({
            id: `${wf.id}-edge-${stepIndex - 1}-${stepIndex}`,
            source: `${wf.id}-${stepIndex - 1}`,
            target: `${wf.id}-${stepIndex}`,
            animated: true,
            style: {
              stroke: 'hsl(var(--primary))',
              strokeWidth: 2,
            },
            markerEnd: {
              type: 'arrowclosed',
            },
          });
        }
      });

      // If a workflow has only one step, ensure it still appears
      if (steps.length === 0) {
        const emptyId = `${wf.id}-0`;
        nodes.push({
          id: emptyId,
          type: 'custom',
          position: { x: 0 + wfIndex * 30, y: wfIndex * 200 + 50 },
          data: { label: wf.name || "(empty)", workflow: wf },
        });
      }
    });

    return { nodes, edges };
  }, [workflows]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialData.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialData.edges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  const onConnect = useCallback((params: Connection) => {
    setEdges((eds) => addEdge(params, eds));
  }, [setEdges]);

  const onNodeClick = useCallback((_: any, node: Node) => {
    setSelectedNode(node);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const removeSelectedNode = useCallback(() => {
    if (!selectedNode) return;
    setNodes((n) => n.filter((x) => x.id !== selectedNode.id));
    setEdges((e) => e.filter((ed) => ed.source !== selectedNode.id && ed.target !== selectedNode.id));
    setSelectedNode(null);
  }, [selectedNode, setNodes, setEdges]);

  return (
    <ReactFlowProvider>
      <div className="flex flex-1 gap-4 p-4 pt-0 h-full">
        <div className="flex-1 rounded-xl bg-muted/50 p-2 flex flex-col">
          <div className="flex-1" style={{ minHeight: "0" }}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={onNodeClick}
              onPaneClick={onPaneClick}
              fitView
              colorMode="system"
              style={{ width: "100%", height: "100%" }}
            >
              <Background style={{ backgroundColor: 'transparent' }} />
              <Controls />
            </ReactFlow>
          </div>

          {isLoading && <div className="text-sm text-muted-foreground mt-2">Loading workflows...</div>}
        </div>

        <aside className="w-80 rounded-xl bg-muted/30 p-4">
          <h3 className="font-semibold mb-4">Node Details</h3>
          {selectedNode ? (
            <div className="space-y-4">
              <SidebarSection
                title={(selectedNode.data as NodeData)?.step?.name || (selectedNode.data as NodeData)?.label || "Unnamed Node"}
              >
                <InfoDisplay
                  items={[
                    { key: "ID", value: selectedNode.id },
                    ...((selectedNode.data as NodeData)?.step?.tool ? [{ key: "Tool", value: (selectedNode.data as NodeData).step!.tool! }] : []),
                    ...((selectedNode.data as NodeData)?.workflow?.name ? [{ key: "Workflow", value: (selectedNode.data as NodeData).workflow!.name! }] : []),
                  ]}
                />
              </SidebarSection>

              {(selectedNode.data as NodeData)?.step?.description && (
                <SidebarSection title="Description">
                  <p className="text-sm text-muted-foreground">{(selectedNode.data as NodeData).step!.description}</p>
                </SidebarSection>
              )}

              <SidebarSection title="Position">
                <InfoDisplay
                  items={[
                    { key: "X", value: Math.round(selectedNode.position.x).toString() },
                    { key: "Y", value: Math.round(selectedNode.position.y).toString() },
                  ]}
                />
              </SidebarSection>

              <div className="flex gap-2">
                <button
                  onClick={removeSelectedNode}
                  className="px-3 py-1 text-sm bg-destructive text-destructive-foreground rounded hover:bg-destructive/90 transition-colors"
                >
                  Remove Node
                </button>
              </div>
            </div>
          ) : (
            <EmptyState message="Click a node to view its details" />
          )}

          <div className="mt-6">
            <h4 className="font-medium mb-3">Workflows</h4>
            <div className="space-y-2">
              {workflows.length === 0 && (
                <EmptyState message="No workflows found" />
              )}
              {workflows.map((wf) => (
                <WorkflowCard
                  key={wf.id}
                  id={wf.id}
                  name={wf.name}
                  stepCount={(wf.steps || []).length}
                />
              ))}
            </div>
          </div>
        </aside>
      </div>
    </ReactFlowProvider>
  );
}
