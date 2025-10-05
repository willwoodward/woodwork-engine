"use client";

import { useCallback, useMemo, useEffect, useState } from "react";
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
  getBezierPath,
  BaseEdge,
} from "@xyflow/react";
import type { Node, Edge, EdgeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Plus, Webhook, Filter } from "lucide-react";
import { PipelineNode } from "@/components/ui";

// Event execution order (from backend code analysis)
const EVENT_EXECUTION_ORDER = [
  "input.received",
  "agent.thought",
  "agent.action",
  "tool.call",
  "tool.observation",
  "agent.step_complete",
  "agent.error",
  "user.input.request",
  "user.input.response",
  "agent.response",
];

// Custom edge with hover-to-add functionality
function CustomEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data,
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const [isHovered, setIsHovered] = useState(false);

  const handleAddHook = () => {
    if (data?.onAddHook) {
      data.onAddHook(data.sourceEvent, data.targetEvent);
    }
  };

  const handleAddPipe = () => {
    if (data?.onAddPipe) {
      data.onAddPipe(data.sourceEvent, data.targetEvent);
    }
  };

  return (
    <>
      <BaseEdge path={edgePath} markerEnd={markerEnd} style={style} />
      <path
        d={edgePath}
        fill="none"
        stroke="transparent"
        strokeWidth={20}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      />
      {isHovered && (
        <g transform={`translate(${labelX}, ${labelY})`}>
          {/* Background */}
          <rect
            x={-60}
            y={-20}
            width={120}
            height={40}
            fill="hsl(var(--background))"
            stroke="hsl(var(--border))"
            strokeWidth={2}
            rx={8}
          />
          {/* Add Hook button */}
          <g
            transform="translate(-35, 0)"
            onClick={handleAddHook}
            style={{ cursor: "pointer" }}
          >
            <circle r={12} fill="#3b82f6" />
            <text
              fill="white"
              fontSize={10}
              textAnchor="middle"
              dy={-18}
              fontWeight={600}
            >
              Hook
            </text>
            <path
              d="M -4 0 L 4 0 M 0 -4 L 0 4"
              stroke="white"
              strokeWidth={2}
            />
          </g>
          {/* Add Pipe button */}
          <g
            transform="translate(35, 0)"
            onClick={handleAddPipe}
            style={{ cursor: "pointer" }}
          >
            <circle r={12} fill="#a855f7" />
            <text
              fill="white"
              fontSize={10}
              textAnchor="middle"
              dy={-18}
              fontWeight={600}
            >
              Pipe
            </text>
            <path
              d="M -4 0 L 4 0 M 0 -4 L 0 4"
              stroke="white"
              strokeWidth={2}
            />
          </g>
        </g>
      )}
    </>
  );
}

// Event node component
const EventNode = ({ data }: { data: any }) => {
  const Icon = data.icon || Webhook;

  return (
    <div className="relative">
      <Handle
        type="target"
        position={Position.Left}
        style={{ background: "#6b7280", border: "2px solid #374151" }}
      />
      <Handle
        type="source"
        position={Position.Right}
        style={{ background: "#6b7280", border: "2px solid #374151" }}
      />
      <PipelineNode
        icon={Icon}
        label={data.label}
        count={data.count}
        variant="event"
        className="shadow-md"
      />
    </div>
  );
};

// Hook/Pipe node on edge
const ListenerNode = ({ data }: { data: any }) => {
  const Icon = data.variant === "hook" ? Webhook : Filter;

  return (
    <div className="relative">
      <Handle
        type="target"
        position={Position.Left}
        style={{
          background: data.variant === "hook" ? "#3b82f6" : "#a855f7",
          border: `2px solid ${data.variant === "hook" ? "#1e40af" : "#7e22ce"}`,
        }}
      />
      <Handle
        type="source"
        position={Position.Right}
        style={{
          background: data.variant === "hook" ? "#3b82f6" : "#a855f7",
          border: `2px solid ${data.variant === "hook" ? "#1e40af" : "#7e22ce"}`,
        }}
      />
      <PipelineNode
        icon={Icon}
        label={data.label}
        variant={data.variant}
        className="shadow-sm"
      />
    </div>
  );
};

const nodeTypes = {
  event: EventNode,
  listener: ListenerNode,
};

const edgeTypes = {
  custom: CustomEdge,
};

export interface EventPipelineData {
  hooks: Record<string, Array<{ function: string; module: string }>>;
  pipes: Record<string, Array<{ function: string; module: string }>>;
  event_types: string[];
}

interface EventPipelineGraphProps {
  data: EventPipelineData;
  onNodeClick?: (node: Node) => void;
  onAddHook?: (fromEvent: string, toEvent: string) => void;
  onAddPipe?: (fromEvent: string, toEvent: string) => void;
  className?: string;
}

/**
 * Event pipeline graph with left-to-right event flow
 * Shows hooks and pipes between events with hover-to-add functionality
 */
export function EventPipelineGraph({
  data,
  onNodeClick,
  onAddHook,
  onAddPipe,
  className,
}: EventPipelineGraphProps) {
  // Build graph with events in execution order
  const { initialNodes, initialEdges } = useMemo(() => {
    if (!data?.event_types || data.event_types.length === 0) {
      return { initialNodes: [], initialEdges: [] };
    }

    const nodes: Node[] = [];
    const edges: Edge[] = [];

    // Track modules for grouping
    const moduleGroups: Record<string, { hooks: number; pipes: number }> = {};

    // Sort events by execution order
    const sortedEvents = [...data.event_types].sort((a, b) => {
      const aIndex = EVENT_EXECUTION_ORDER.indexOf(a);
      const bIndex = EVENT_EXECUTION_ORDER.indexOf(b);
      if (aIndex === -1 && bIndex === -1) return 0;
      if (aIndex === -1) return 1;
      if (bIndex === -1) return -1;
      return aIndex - bIndex;
    });

    const EVENT_SPACING_X = 350;
    const EVENT_SPACING_Y = 150;
    const LISTENER_OFFSET_Y = 100;

    // Create event nodes in left-to-right order
    sortedEvents.forEach((eventName, index) => {
      const hooks = data.hooks[eventName] || [];
      const pipes = data.pipes[eventName] || [];

      // Add event node
      const eventNodeId = `event-${eventName}`;
      nodes.push({
        id: eventNodeId,
        type: "event",
        position: { x: index * EVENT_SPACING_X, y: 200 },
        data: {
          label: eventName,
          icon: Webhook,
          count: hooks.length + pipes.length,
          eventName,
        },
      });

      // Add hooks as nodes above the event flow
      hooks.forEach((hook, hookIndex) => {
        const hookNodeId = `hook-${eventName}-${hookIndex}`;
        nodes.push({
          id: hookNodeId,
          type: "listener",
          position: {
            x: index * EVENT_SPACING_X,
            y: 200 - LISTENER_OFFSET_Y - hookIndex * 70,
          },
          data: {
            label: hook.function,
            module: hook.module,
            variant: "hook",
            eventName,
          },
        });

        // Connect hook to event (hooks run when event fires)
        edges.push({
          id: `edge-${eventNodeId}-${hookNodeId}`,
          source: eventNodeId,
          target: hookNodeId,
          type: "default",
          animated: true,
          style: { stroke: "#3b82f6", strokeWidth: 2 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: "#3b82f6",
            width: 10,
            height: 10,
          },
        });
      });

      // Add pipes as nodes below the event flow
      pipes.forEach((pipe, pipeIndex) => {
        const pipeNodeId = `pipe-${eventName}-${pipeIndex}`;
        nodes.push({
          id: pipeNodeId,
          type: "listener",
          position: {
            x: index * EVENT_SPACING_X,
            y: 200 + LISTENER_OFFSET_Y + pipeIndex * 70,
          },
          data: {
            label: pipe.function,
            module: pipe.module,
            variant: "pipe",
            eventName,
          },
        });

        // Connect event to pipe (pipes transform event data)
        edges.push({
          id: `edge-${eventNodeId}-${pipeNodeId}`,
          source: eventNodeId,
          target: pipeNodeId,
          type: "default",
          animated: true,
          style: { stroke: "#a855f7", strokeWidth: 2 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: "#a855f7",
            width: 10,
            height: 10,
          },
        });
      });

      // Connect event to next event in flow
      if (index < sortedEvents.length - 1) {
        const nextEventName = sortedEvents[index + 1];
        const nextEventNodeId = `event-${nextEventName}`;

        edges.push({
          id: `flow-${eventNodeId}-${nextEventNodeId}`,
          source: eventNodeId,
          target: nextEventNodeId,
          type: "custom",
          style: { stroke: "#6b7280", strokeWidth: 3 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: "#6b7280",
            width: 12,
            height: 12,
          },
          data: {
            sourceEvent: eventName,
            targetEvent: nextEventName,
            onAddHook,
            onAddPipe,
          },
        });
      }
    });

    return { initialNodes: nodes, initialEdges: edges };
  }, [data, onAddHook, onAddPipe]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Update nodes and edges when data changes
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

  if (!data?.event_types || data.event_types.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        No events registered
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
          edgeTypes={edgeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          defaultEdgeOptions={{
            style: { strokeWidth: 3 },
            markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12 },
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
