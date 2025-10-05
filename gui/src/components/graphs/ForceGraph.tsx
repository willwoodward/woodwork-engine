import { useRef, useEffect, useCallback, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import type { ForceGraphMethods, NodeObject } from 'react-force-graph-2d';

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  group?: string;
  color?: string;
  size?: number;
  metadata?: Record<string, any>;
}

export interface GraphLink {
  source: string;
  target: string;
  type?: string;
  label?: string;
  color?: string;
  width?: number;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

interface ForceGraphProps {
  data: GraphData;
  onNodeClick?: (node: GraphNode) => void;
  onNodeHover?: (node: GraphNode | null) => void;
  highlightedNodeId?: string | null;
  className?: string;
  nodeColorMap?: Record<string, string>;
  linkColorMap?: Record<string, string>;
}

const DEFAULT_NODE_COLORS: Record<string, string> = {
  agent: '#f59e0b',       // orange/amber
  prompt: '#3b82f6',      // blue
  action: '#10b981',      // green
  workflow: '#8b5cf6',    // purple
  default: '#6b7280',     // gray
};

const DEFAULT_LINK_COLORS: Record<string, string> = {
  executes: '#f59e0b',    // orange (agent -> workflow)
  starts: '#3b82f6',      // blue
  next: '#10b981',        // green
  depends_on: '#a855f7',  // purple
  default: '#9ca3af',     // gray
};

export function ForceGraph({
  data,
  onNodeClick,
  onNodeHover,
  highlightedNodeId,
  className = '',
  nodeColorMap = DEFAULT_NODE_COLORS,
  linkColorMap = DEFAULT_LINK_COLORS,
}: ForceGraphProps) {
  const fgRef = useRef<ForceGraphMethods | undefined>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);
  const highlightNodes = useRef(new Set<string>());
  const highlightLinks = useRef(new Set<string>());
  const hoverNode = useRef<NodeObject | null>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [internalGraphData, setInternalGraphData] = useState<{nodes: any[], links: any[]}>({ nodes: [], links: [] });

  // Measure container and update dimensions
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const { width, height } = containerRef.current.getBoundingClientRect();
        setDimensions({ width, height });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  // Incrementally update graph data - only add new nodes/links, preserve existing ones
  useEffect(() => {
    setInternalGraphData(prev => {
      // Build a map of existing nodes by ID
      const existingNodesMap = new Map(prev.nodes.map((n: any) => [n.id, n]));
      const existingLinkIds = new Set(prev.links.map((l: any) => {
        const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
        const targetId = typeof l.target === 'object' ? l.target.id : l.target;
        return `${sourceId}-${targetId}`;
      }));

      // Find new nodes and create them
      const nodesToAdd: any[] = [];
      data.nodes.forEach(node => {
        if (!existingNodesMap.has(node.id)) {
          nodesToAdd.push({
            id: node.id,
            name: node.label,
            type: node.type,
            group: node.group,
            color: node.color || nodeColorMap[node.type] || nodeColorMap.default,
            val: node.size || 1,
            ...node.metadata,
          });
        }
      });

      // Find new links
      const linksToAdd: any[] = [];
      data.links.forEach(link => {
        const linkId = `${link.source}-${link.target}`;
        if (!existingLinkIds.has(linkId)) {
          linksToAdd.push({
            source: link.source,
            target: link.target,
            type: link.type,
            label: link.label,
            color: link.color || linkColorMap[link.type || 'default'] || linkColorMap.default,
            width: link.width || 1,
          });
        }
      });

      // Only update if there are actual new items
      if (nodesToAdd.length === 0 && linksToAdd.length === 0) {
        return prev; // Return exact same object reference - graph won't update
      }

      // Return new object with existing nodes (same references) + new nodes
      return {
        nodes: [...prev.nodes, ...nodesToAdd],
        links: [...prev.links, ...linksToAdd],
      };
    });
  }, [data, nodeColorMap, linkColorMap]);

  // Handle node highlighting
  const updateHighlight = useCallback(() => {
    highlightNodes.current.clear();
    highlightLinks.current.clear();

    if (hoverNode.current) {
      highlightNodes.current.add(hoverNode.current.id as string);

      // Highlight connected links
      internalGraphData.links.forEach((link: any) => {
        if (link.source.id === hoverNode.current?.id || link.target.id === hoverNode.current?.id) {
          highlightLinks.current.add(`${link.source.id}-${link.target.id}`);
          highlightNodes.current.add(link.source.id);
          highlightNodes.current.add(link.target.id);
        }
      });
    }

    // Also highlight selected node
    if (highlightedNodeId) {
      highlightNodes.current.add(highlightedNodeId);
    }
  }, [internalGraphData.links, highlightedNodeId]);

  // Update highlight when hover or selection changes
  useEffect(() => {
    updateHighlight();
  }, [updateHighlight]);

  // Configure d3 forces for tighter clustering
  useEffect(() => {
    if (fgRef.current) {
      const fg = fgRef.current;

      // Reduce charge (repulsion) force between nodes
      fg.d3Force('charge')?.strength(-30);

      // Set link distance
      fg.d3Force('link')?.distance(50);

      // Weak center force
      fg.d3Force('center')?.strength(0.05);
    }
  }, []);

  // Handle node click
  const handleNodeClick = useCallback((node: NodeObject) => {
    if (onNodeClick) {
      onNodeClick(node as GraphNode);
    }
  }, [onNodeClick]);

  // Handle node hover
  const handleNodeHover = useCallback((node: NodeObject | null) => {
    hoverNode.current = node;
    updateHighlight();
    if (onNodeHover) {
      onNodeHover(node as GraphNode | null);
    }
  }, [onNodeHover, updateHighlight]);

  // Paint node canvas
  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = node.name || node.id;
    const fontSize = 12 / globalScale;
    const nodeSize = node.val || 5;

    // Determine if this node is highlighted
    const isHighlighted = highlightNodes.current.has(node.id) || highlightedNodeId === node.id;

    // Draw node circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, nodeSize, 0, 2 * Math.PI, false);
    ctx.fillStyle = node.color || '#999';
    ctx.fill();

    // Draw highlight ring if highlighted
    if (isHighlighted) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, nodeSize + 2, 0, 2 * Math.PI, false);
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2 / globalScale;
      ctx.stroke();
    }

    // Draw label
    ctx.font = `${fontSize}px Sans-Serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = isHighlighted ? '#fff' : '#ddd';
    ctx.fillText(label, node.x, node.y + nodeSize + fontSize);
  }, [highlightedNodeId]);

  // Paint link canvas
  const paintLink = useCallback((link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const linkId = `${link.source.id}-${link.target.id}`;
    const isHighlighted = highlightLinks.current.has(linkId);

    // Draw link
    ctx.beginPath();
    ctx.moveTo(link.source.x, link.source.y);
    ctx.lineTo(link.target.x, link.target.y);
    ctx.strokeStyle = isHighlighted ? link.color : `${link.color}80`; // Add transparency when not highlighted
    ctx.lineWidth = (link.width || 1) * (isHighlighted ? 2 : 1) / globalScale;
    ctx.stroke();

    // Draw arrow
    if (isHighlighted) {
      const arrowLength = 8 / globalScale;
      const arrowWidth = 4 / globalScale;

      const angle = Math.atan2(link.target.y - link.source.y, link.target.x - link.source.x);
      const targetNodeSize = link.target.val || 5;

      const arrowX = link.target.x - Math.cos(angle) * targetNodeSize;
      const arrowY = link.target.y - Math.sin(angle) * targetNodeSize;

      ctx.save();
      ctx.translate(arrowX, arrowY);
      ctx.rotate(angle);

      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(-arrowLength, arrowWidth);
      ctx.lineTo(-arrowLength, -arrowWidth);
      ctx.closePath();

      ctx.fillStyle = link.color;
      ctx.fill();
      ctx.restore();
    }
  }, []);

  return (
    <div ref={containerRef} className={className} style={{ width: '100%', height: '100%' }}>
      {internalGraphData.nodes.length > 0 && (
        <ForceGraph2D
          ref={fgRef}
          graphData={internalGraphData}
          width={dimensions.width}
          height={dimensions.height}
          nodeLabel="name"
          nodeCanvasObject={paintNode}
          linkCanvasObject={paintLink}
          onNodeClick={handleNodeClick}
          onNodeHover={handleNodeHover}
          linkDirectionalParticles={2}
          linkDirectionalParticleWidth={2}
          linkDirectionalParticleSpeed={0.005}
          cooldownTicks={100}
          warmupTicks={50}
          enableNodeDrag={true}
          enableZoomInteraction={true}
          enablePanInteraction={true}
          d3AlphaDecay={0.02}
          d3VelocityDecay={0.3}
        />
      )}
    </div>
  );
}
