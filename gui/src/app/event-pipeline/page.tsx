"use client"

import { useState } from "react";
import type { Node } from "@xyflow/react";
import { Clock } from "lucide-react";
import {
  SidebarSection,
  InfoDisplay,
  EmptyState,
} from "@/components/ui";
import { useEventPipeline } from "@/hooks/useEventPipeline";
import { EventPipelineGraph } from "@/components/event-pipeline/event-pipeline-graph";

// Mock data for development
const MOCK_PIPELINE_DATA = {
  event_types: ["input.received", "agent.thought", "agent.action", "tool.call", "tool.observation", "agent.step_complete"],
  hooks: {
    "input.received": [{ function: "log_input", module: "woodwork.hooks" }],
    "agent.thought": [{ function: "log_thought", module: "woodwork.hooks" }],
    "agent.action": [{ function: "log_action", module: "woodwork.hooks" }, { function: "track_action", module: "woodwork.tracking" }],
    "tool.call": [{ function: "log_tool_call", module: "woodwork.hooks" }],
  },
  pipes: {
    "input.received": [{ function: "sanitize_input", module: "woodwork.pipes" }],
  }
};

const USE_MOCK_DATA = false; // Toggle this for development

export default function EventPipelinePage() {
  const { data: fetchedData, isLoading, error } = useEventPipeline();
  const pipelineData = USE_MOCK_DATA ? MOCK_PIPELINE_DATA : fetchedData;
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  const handleAddHook = (fromEvent: string, toEvent: string) => {
    console.log(`Add hook between ${fromEvent} and ${toEvent}`);
    // TODO: Implement hook creation UI
  };

  const handleAddPipe = (fromEvent: string, toEvent: string) => {
    console.log(`Add pipe between ${fromEvent} and ${toEvent}`);
    // TODO: Implement pipe creation UI
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <Clock className="w-8 h-8 animate-spin mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">Loading event pipeline...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <EmptyState message="Failed to load event pipeline. Make sure the AI agent is running." />
      </div>
    );
  }

  return (
    <div className="flex flex-1 gap-4 p-4 pt-0 h-full">
      {/* Graph View */}
      <div className="flex-1 rounded-xl bg-muted/50 p-4 flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-semibold text-lg">Event Pipeline</h3>
            <p className="text-sm text-muted-foreground">
              Agent lifecycle events flow left-to-right • Hover over arrows to add hooks/pipes
            </p>
          </div>
          <div className="text-xs text-muted-foreground">
            {pipelineData?.event_types.length || 0} events •{' '}
            {Object.values(pipelineData?.hooks || {}).flat().length || 0} hooks •{' '}
            {Object.values(pipelineData?.pipes || {}).flat().length || 0} pipes
          </div>
        </div>

        <div className="flex-1" style={{ minHeight: "0" }}>
          {!pipelineData || !pipelineData.event_types || pipelineData.event_types.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <EmptyState message="No event listeners registered" />
            </div>
          ) : (
            <EventPipelineGraph
              data={pipelineData}
              onNodeClick={setSelectedNode}
              onAddHook={handleAddHook}
              onAddPipe={handleAddPipe}
              className="w-full h-full"
            />
          )}
        </div>
      </div>

      {/* Sidebar */}
      <aside className="w-80 rounded-xl bg-muted/30 p-4 space-y-4 overflow-auto">
        {selectedNode ? (
          <>
            <SidebarSection title="Node Details">
              <InfoDisplay
                items={[
                  { key: "Type", value: String(selectedNode.type || "unknown") },
                  { key: "Name", value: String(selectedNode.data.label) },
                  ...(selectedNode.data.module ? [{ key: "Module", value: String(selectedNode.data.module) }] : []),
                  ...(selectedNode.data.eventName ? [{ key: "Event", value: String(selectedNode.data.eventName) }] : []),
                  ...(selectedNode.data.count !== undefined && selectedNode.data.count !== null ? [{ key: "Listeners", value: String(selectedNode.data.count) }] : []),
                ]}
              />
            </SidebarSection>

            {selectedNode.type === 'event' && (
              <SidebarSection title="Event Info">
                <p className="text-sm text-muted-foreground">
                  This event is emitted during agent execution. It has {String(selectedNode.data.count || 0)} listener(s) attached.
                </p>
              </SidebarSection>
            )}

            {selectedNode.data.variant === 'hook' && (
              <SidebarSection title="Hook Info">
                <p className="text-sm text-muted-foreground">
                  Hooks run concurrently when events fire. They're read-only and useful for logging, debugging, and side effects.
                </p>
              </SidebarSection>
            )}

            {selectedNode.data.variant === 'pipe' && (
              <SidebarSection title="Pipe Info">
                <p className="text-sm text-muted-foreground">
                  Pipes transform event data sequentially. They can modify payloads before they reach the next stage.
                </p>
              </SidebarSection>
            )}
          </>
        ) : (
          <EmptyState message="Click a node to view details" />
        )}

        <SidebarSection title="How to Use">
          <p className="text-sm text-muted-foreground">
            Hover over the gray arrows between events to add hooks or pipes inline in the execution flow.
          </p>
        </SidebarSection>
      </aside>
    </div>
  );
}
