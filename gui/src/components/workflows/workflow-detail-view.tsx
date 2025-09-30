"use client";

import React, { useCallback, useMemo, useState, useEffect } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  MarkerType,
  Handle,
  Position,
} from "@xyflow/react";
import type { Node, Edge } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Calendar, Clock, ArrowRight, Database, Zap } from "lucide-react";
import { useWorkflowDetail, type WorkflowDetail } from "@/hooks/useWorkflowDetail";
import { SidebarSection, InfoDisplay, EmptyState } from "@/components/ui";

// Custom node components for different types
const PromptNode = ({ data }: { data: any }) => (
  <div className="relative">
    <Handle
      type="source"
      position={Position.Right}
      style={{ background: '#3b82f6', border: '2px solid #1e40af' }}
    />
    <div className="flex items-center gap-2 px-4 py-3 bg-blue-500/20 text-blue-600 dark:text-blue-400 border-2 border-blue-500/30 rounded-lg shadow-md min-w-[200px]">
      <Database className="w-5 h-5 flex-shrink-0" />
      <div>
        <div className="font-semibold text-sm">Input</div>
        <div className="text-xs">{data.label}</div>
      </div>
    </div>
  </div>
);

const ActionNode = ({ data }: { data: any }) => (
  <div className="relative">
    <Handle
      type="target"
      position={Position.Left}
      style={{ background: '#10b981', border: '2px solid #047857' }}
    />
    <Handle
      type="source"
      position={Position.Right}
      style={{ background: '#10b981', border: '2px solid #047857' }}
    />
    <div className="flex items-center gap-2 px-4 py-3 bg-green-500/20 text-green-600 dark:text-green-400 border-2 border-green-500/30 rounded-lg shadow-md min-w-[200px]">
      <Zap className="w-5 h-5 flex-shrink-0" />
      <div>
        <div className="font-semibold text-sm">{data.tool}</div>
        <div className="text-xs">{data.action}</div>
      </div>
    </div>
  </div>
);

const nodeTypes = {
  prompt: PromptNode,
  action: ActionNode,
};

interface WorkflowDetailViewProps {
  workflowId: string;
  onBack?: () => void;
}

export default function WorkflowDetailView({ workflowId, onBack }: WorkflowDetailViewProps) {
  const { data: workflow, isLoading, error } = useWorkflowDetail(workflowId);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  // Visibility toggles
  const [visibility, setVisibility] = useState({
    promptNodes: true,
    actionNodes: true,
    startsEdges: true,
    nextEdges: true,
    dependencyEdges: true,
  });

  const toggleVisibility = (key: keyof typeof visibility) => {
    setVisibility(prev => ({ ...prev, [key]: !prev[key] }));
  };

  // Convert workflow graph data to ReactFlow format
  const { nodes: initialNodes, edges: initialEdges } = useMemo(() => {
    console.log("WorkflowDetailView: Processing workflow data", {
      workflowId,
      workflow: workflow?.id,
      hasGraph: !!workflow?.graph
    });

    if (!workflow?.graph) {
      console.log("WorkflowDetailView: No workflow graph data available");
      return { nodes: [], edges: [] };
    }

    console.log("WorkflowDetailView: Raw graph data", workflow.graph);
    console.log("WorkflowDetailView: Graph nodes", workflow.graph.nodes);
    console.log("WorkflowDetailView: Graph edges", workflow.graph.edges);

    // Improved automatic layout
    const layoutNodes = (nodes: any[], edges: any[]) => {
      const nodeMap = new Map(nodes.map(n => [n.id, n]));
      const promptNode = nodes.find(n => n.type === 'prompt');
      const actionNodes = nodes.filter(n => n.type === 'action');

      // Sort action nodes by their sequence if available, or by dependencies
      const sortedActions = actionNodes.sort((a, b) => {
        // Try to find edges that show the flow
        const aHasIncoming = edges.some(e => e.target === a.id && e.type === 'starts');
        const bHasIncoming = edges.some(e => e.target === b.id && e.type === 'starts');

        if (aHasIncoming && !bHasIncoming) return -1;
        if (!aHasIncoming && bHasIncoming) return 1;

        return a.id.localeCompare(b.id);
      });

      const positioned = [];
      const nodeSpacing = 280;
      const levelSpacing = 120;

      // Position prompt node
      if (promptNode) {
        positioned.push({
          ...promptNode,
          position: { x: 0, y: 0 }
        });
      }

      // Position action nodes in a flow
      sortedActions.forEach((node, index) => {
        positioned.push({
          ...node,
          position: {
            x: (index + 1) * nodeSpacing,
            y: index % 2 === 0 ? 0 : levelSpacing
          }
        });
      });

      return positioned;
    };

    const nodes: Node[] = layoutNodes(workflow.graph.nodes, workflow.graph.edges).map((node) => ({
      id: node.id,
      type: node.type,
      position: node.position,
      data: {
        label: node.label,
        type: node.type,
        tool: node.type === 'action' ? node.label.split(':')[0] : undefined,
        action: node.type === 'action' ? node.label.split(':')[1] : undefined,
      },
    }));

    const nodeIds = new Set(nodes.map(n => n.id));
    console.log("WorkflowDetailView: Available node IDs", Array.from(nodeIds));

    const edges: Edge[] = workflow.graph.edges
      .filter((edge) => {
        const sourceExists = nodeIds.has(edge.source);
        const targetExists = nodeIds.has(edge.target);
        if (!sourceExists || !targetExists) {
          console.warn("WorkflowDetailView: Skipping edge with missing nodes", {
            edgeId: edge.id,
            source: edge.source,
            target: edge.target,
            sourceExists,
            targetExists
          });
          return false;
        }
        return true;
      })
      .map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: 'default',
        animated: edge.type === 'next',
        style: {
          stroke: edge.type === 'depends_on' ? '#ffffff' : edge.type === 'starts' ? '#3b82f6' : '#10b981',
          strokeWidth: 3,
          strokeDasharray: edge.type === 'depends_on' ? '8,4' : undefined,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: edge.type === 'depends_on' ? '#ffffff' : edge.type === 'starts' ? '#3b82f6' : '#10b981',
          width: 12,
          height: 12,
        },
        label: edge.type === 'depends_on' ? 'depends on' : edge.type === 'starts' ? 'starts' : '',
        labelStyle: {
          fill: '#ffffff',
          fontSize: 12,
          fontWeight: 500,
          fontFamily: 'system-ui',
        },
        labelBgStyle: {
          fill: '#000000',
          fillOpacity: 0.8,
        },
      }));

    console.log("WorkflowDetailView: Generated nodes and edges", {
      nodes: nodes.length,
      edges: edges.length,
      nodeIds: nodes.map(n => n.id),
      edgeDetails: edges.map(e => ({
        id: e.id,
        source: e.source,
        target: e.target,
        type: e.type,
        style: e.style,
        markerEnd: e.markerEnd
      }))
    });

    console.log("WorkflowDetailView: Full edge data", edges);

    return { nodes, edges };
  }, [workflow]);

  // Filter nodes and edges based on visibility
  const filteredNodes = useMemo(() => {
    return initialNodes.filter(node => {
      if (node.type === 'prompt' && !visibility.promptNodes) return false;
      if (node.type === 'action' && !visibility.actionNodes) return false;
      return true;
    });
  }, [initialNodes, visibility]);

  const filteredEdges = useMemo(() => {
    return initialEdges.filter(edge => {
      if (edge.type === 'default') {
        // Check the edge data to determine the actual edge type
        const edgeData = workflow?.graph?.edges.find(e => e.id === edge.id);
        if (edgeData?.type === 'starts' && !visibility.startsEdges) return false;
        if (edgeData?.type === 'next' && !visibility.nextEdges) return false;
        if (edgeData?.type === 'depends_on' && !visibility.dependencyEdges) return false;
      }
      return true;
    });
  }, [initialEdges, visibility, workflow]);

  const [nodes, setNodes, onNodesChange] = useNodesState(filteredNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(filteredEdges);

  // Update nodes and edges when workflow data or visibility changes
  useEffect(() => {
    console.log("WorkflowDetailView: Updating ReactFlow with", {
      nodeCount: filteredNodes.length,
      edgeCount: filteredEdges.length
    });
    setNodes(filteredNodes);
    setEdges(filteredEdges);
  }, [filteredNodes, filteredEdges, setNodes, setEdges]);

  // Debug: Log edges state changes
  useEffect(() => {
    console.log("WorkflowDetailView: Edges state updated", {
      edgeCount: edges.length,
      edgeIds: edges.map(e => e.id)
    });
  }, [edges]);

  const onNodeClick = useCallback((_: any, node: Node) => {
    setSelectedNode(node);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

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
          <ReactFlowProvider>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={onNodeClick}
              onPaneClick={onPaneClick}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              defaultEdgeOptions={{
                style: { strokeWidth: 3 },
                markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12 }
              }}
              style={{ width: "100%", height: "100%" }}
            >
              <Background />
              <Controls />
            </ReactFlow>
          </ReactFlowProvider>
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
                  { key: "Type", value: selectedNode.data.type },
                  { key: "ID", value: selectedNode.id },
                  ...(selectedNode.data.tool ? [{ key: "Tool", value: selectedNode.data.tool }] : []),
                  ...(selectedNode.data.action ? [{ key: "Action", value: selectedNode.data.action }] : []),
                ]}
              />
            </SidebarSection>
          )}

          <SidebarSection title="Legend & Visibility">
            <div className="space-y-2 text-xs">
              {/* Node Types */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-blue-500/20 rounded border border-blue-500/30"></div>
                  <span>Input/Prompt</span>
                </div>
                <button
                  onClick={() => toggleVisibility('promptNodes')}
                  className={`w-4 h-4 rounded border ${
                    visibility.promptNodes
                      ? 'bg-blue-500 border-blue-600'
                      : 'bg-muted border-border'
                  }`}
                />
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-green-500/20 rounded border border-green-500/30"></div>
                  <span>Action/Step</span>
                </div>
                <button
                  onClick={() => toggleVisibility('actionNodes')}
                  className={`w-4 h-4 rounded border ${
                    visibility.actionNodes
                      ? 'bg-green-500 border-green-600'
                      : 'bg-muted border-border'
                  }`}
                />
              </div>

              {/* Edge Types */}
              <div className="mt-3 pt-2 border-t border-border">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-0.5" style={{ backgroundColor: '#3b82f6' }}></div>
                    <span>Starts</span>
                  </div>
                  <button
                    onClick={() => toggleVisibility('startsEdges')}
                    className={`w-4 h-4 rounded border ${
                      visibility.startsEdges
                        ? 'bg-blue-500 border-blue-600'
                        : 'bg-muted border-border'
                    }`}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-0.5" style={{ backgroundColor: '#10b981' }}></div>
                    <span>Next Step</span>
                  </div>
                  <button
                    onClick={() => toggleVisibility('nextEdges')}
                    className={`w-4 h-4 rounded border ${
                      visibility.nextEdges
                        ? 'bg-green-500 border-green-600'
                        : 'bg-muted border-border'
                    }`}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-0.5 border-dashed border-t-2" style={{ borderColor: '#ffffff', backgroundColor: '#ffffff' }}></div>
                    <span>Dependency</span>
                  </div>
                  <button
                    onClick={() => toggleVisibility('dependencyEdges')}
                    className={`w-4 h-4 rounded border ${
                      visibility.dependencyEdges
                        ? 'bg-white border-gray-300'
                        : 'bg-muted border-border'
                    }`}
                  />
                </div>
              </div>
            </div>
          </SidebarSection>
        </aside>
      </div>
    </div>
  );
}