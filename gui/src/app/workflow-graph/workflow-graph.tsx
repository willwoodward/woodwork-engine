"use client"

import React, { useCallback, useEffect, useMemo, useState } from "react";
import ReactFlow, {
  ReactFlowProvider,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  Background,
  Controls,
  Node,
  Edge,
  Connection,
  NodeChange,
  EdgeChange,
  OnNodesChange,
  OnEdgesChange,
} from "reactflow";
import "reactflow/dist/style.css";

import { useWorkflows } from "@/hooks/useWorkflows";

export default function WorkflowGraphPage() {
  const { data: workflows = [], isLoading } = useWorkflows();

  const buildNodesAndEdges = useCallback(() => {
    const nodes: Node[] = [];
    const edges: Edge[] = [];

    workflows.forEach((wf, wfIndex) => {
      const steps = wf.steps || [];

      steps.forEach((step, stepIndex) => {
        const id = `${wf.id}-${stepIndex}`;
        nodes.push({
          id,
          position: { x: 150 * stepIndex + wfIndex * 20, y: wfIndex * 160 + 50 },
          data: {
            label: step.name || step.tool || `Step ${stepIndex + 1}`,
            step,
            workflow: wf,
          },
          style: {
            minWidth: 160,
            padding: 8,
          },
        });

        if (stepIndex > 0) {
          edges.push({
            id: `${wf.id}-edge-${stepIndex - 1}-${stepIndex}`,
            source: `${wf.id}-${stepIndex - 1}`,
            target: `${wf.id}-${stepIndex}`,
            animated: true,
          });
        }
      });

      // If a workflow has only one step, ensure it still appears
      if (steps.length === 0) {
        const emptyId = `${wf.id}-0`;
        nodes.push({
          id: emptyId,
          position: { x: 0 + wfIndex * 20, y: wfIndex * 160 + 50 },
          data: { label: wf.name || "(empty)", workflow: wf },
          style: { minWidth: 160, padding: 8 },
        });
      }
    });

    return { nodes, edges };
  }, [workflows]);

  const initial = useMemo(() => buildNodesAndEdges(), [buildNodesAndEdges]);

  const [nodes, setNodes] = useState<Node[]>(initial.nodes);
  const [edges, setEdges] = useState<Edge[]>(initial.edges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  // When workflows update (new workflows added), update nodes/edges
  useEffect(() => {
    const { nodes: newNodes, edges: newEdges } = buildNodesAndEdges();
    setNodes((prev) => {
      // naive replace to keep things simple; ReactFlow will preserve positions if user moved them, but
      // for now we merge by id: keep previous position if available
      const prevMap = new Map(prev.map((n) => [n.id, n]));
      return newNodes.map((n) => {
        const p = prevMap.get(n.id);
        return p ? { ...n, position: p.position } : n;
      });
    });
    setEdges(newEdges);
  }, [workflows, buildNodesAndEdges]);

  const onNodesChange: OnNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((nds) => applyNodeChanges(changes, nds));
  }, []);

  const onEdgesChange: OnEdgesChange = useCallback((changes: EdgeChange[]) => {
    setEdges((eds) => applyEdgeChanges(changes, eds));
  }, []);

  const onConnect = useCallback((connection: Connection) => {
    setEdges((eds) => addEdge(connection, eds));
  }, []);

  const onNodeClick = useCallback((_, node) => {
    setSelectedNode(node);
  }, []);

  const addManualNode = useCallback(() => {
    const id = `manual-${Date.now()}`;
    const newNode: Node = {
      id,
      position: { x: 100 + Math.random() * 400, y: 100 + Math.random() * 200 },
      data: { label: `Manual ${id}` },
      style: { minWidth: 160, padding: 8 },
    };
    setNodes((n) => n.concat(newNode));
  }, []);

  const removeSelectedNode = useCallback(() => {
    if (!selectedNode) return;
    setNodes((n) => n.filter((x) => x.id !== selectedNode.id));
    setEdges((e) => e.filter((ed) => ed.source !== selectedNode.id && ed.target !== selectedNode.id));
    setSelectedNode(null);
  }, [selectedNode]);

  return (
    <ReactFlowProvider>
      <div className="flex flex-1 gap-4 p-4 pt-0">
        <div className="flex-1 min-h-[60vh] rounded-xl bg-muted/50 p-2">
          <div className="flex items-center justify-between gap-2 mb-2">
            <h2 className="text-lg font-semibold">Workflow View</h2>
            <div className="flex items-center gap-2">
              <button onClick={addManualNode} className="btn">Add Node</button>
              <button onClick={() => { /* placeholder for future: open settings */ }} className="btn">Settings</button>
            </div>
          </div>

          <div style={{ width: "100%", height: "70vh" }}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={onNodeClick}
              fitView
            >
              <Background />
              <Controls />
            </ReactFlow>
          </div>

          {isLoading && <div className="text-sm text-muted-foreground mt-2">Loading workflows...</div>}
        </div>

        <aside className="w-80 rounded-xl bg-muted/30 p-4">
          <h3 className="font-semibold mb-2">Details</h3>
          {selectedNode ? (
            <div>
              <div className="mb-2">
                <strong>ID:</strong> {selectedNode.id}
              </div>
              <div className="mb-2">
                <strong>Label:</strong> {String(selectedNode.data?.label ?? "")}
              </div>
              <div className="mb-2">
                <strong>Data:</strong>
                <pre className="text-xs mt-1 whitespace-pre-wrap">{JSON.stringify(selectedNode.data ?? {}, null, 2)}</pre>
              </div>
              <div className="flex gap-2 mt-2">
                <button onClick={removeSelectedNode} className="btn btn-danger">Remove</button>
              </div>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">Click a node to view details</div>
          )}

          <div className="mt-4">
            <h4 className="font-medium">Workflows</h4>
            <div className="text-sm mt-2 max-h-48 overflow-auto">
              {workflows.length === 0 && <div className="text-muted-foreground">No workflows found</div>}
              {workflows.map((wf) => (
                <div key={wf.id} className="mb-2">
                  <div className="font-semibold">{wf.name ?? wf.id}</div>
                  <div className="text-xs text-muted-foreground">{(wf.steps || []).length} steps</div>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </ReactFlowProvider>
  );
}
