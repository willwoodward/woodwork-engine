"use client";

import { useCallback, useMemo, useEffect } from "react";
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
import { Database, Zap } from "lucide-react";

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
        <div className="text-xs truncate max-w-[160px]">{data.label}</div>
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
      <div className="min-w-0">
        <div className="font-semibold text-sm">{data.tool || 'Action'}</div>
        <div className="text-xs truncate max-w-[160px]">{data.action || data.label}</div>
      </div>
    </div>
  </div>
);

const nodeTypes = {
  prompt: PromptNode,
  action: ActionNode,
};

// Graph data structure (matches backend format)
export interface WorkflowGraphNode {
  id: string;
  type: 'prompt' | 'action';
  label: string;
}

export interface WorkflowGraphEdge {
  id: string;
  source: string;
  target: string;
  type: 'starts' | 'next' | 'depends_on';
}

export interface WorkflowGraphData {
  nodes: WorkflowGraphNode[];
  edges: WorkflowGraphEdge[];
}

interface WorkflowGraphProps {
  graph: WorkflowGraphData;
  onNodeClick?: (node: Node) => void;
  className?: string;
}

// Automatic layout algorithm
function layoutNodes(nodes: WorkflowGraphNode[], edges: WorkflowGraphEdge[]) {
  const promptNode = nodes.find(n => n.type === 'prompt');
  const actionNodes = nodes.filter(n => n.type === 'action');

  // Sort action nodes by their sequence in the flow
  const sortedActions = actionNodes.sort((a, b) => {
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
}

/**
 * Reusable workflow graph visualization component
 * Uses ReactFlow to display workflow nodes and edges
 */
export function WorkflowGraph({ graph, onNodeClick, className }: WorkflowGraphProps) {
  // Convert graph data to ReactFlow format
  const { initialNodes, initialEdges } = useMemo(() => {
    if (!graph?.nodes || !graph?.edges) {
      return { initialNodes: [], initialEdges: [] };
    }

    const positionedNodes = layoutNodes(graph.nodes, graph.edges);

    const nodes: Node[] = positionedNodes.map((node) => ({
      id: node.id,
      type: node.type,
      position: node.position,
      data: {
        label: node.label,
        type: node.type,
        tool: node.type === 'action' ? node.label.split(':')[0] : undefined,
        action: node.type === 'action' ? node.label.split(':').slice(1).join(':') : undefined,
      },
    }));

    const nodeIds = new Set(nodes.map(n => n.id));

    const edges: Edge[] = graph.edges
      .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
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

    return { initialNodes: nodes, initialEdges: edges };
  }, [graph]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Update nodes and edges when graph data changes
  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  const handleNodeClick = useCallback(
    (_: any, node: Node) => {
      if (onNodeClick) {
        onNodeClick(node);
      }
    },
    [onNodeClick]
  );

  if (!graph?.nodes || graph.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        No workflow graph data available
      </div>
    );
  }

  return (
    <div className={className}>
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
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
  );
}

/**
 * Simplified workflow graph for small previews
 * No controls, just the visualization
 */
export function WorkflowGraphPreview({ graph, className }: { graph: WorkflowGraphData; className?: string }) {
  if (!graph?.nodes || graph.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        No workflow graph data available
      </div>
    );
  }

  return (
    <div className={className} style={{ width: '100%', height: '100%' }}>
      <WorkflowGraph graph={graph} className="w-full h-full" />
    </div>
  );
}
