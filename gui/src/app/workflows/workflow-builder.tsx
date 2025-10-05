import { useState, useMemo, useEffect } from "react";
import { Save, Play, Trash2 } from "lucide-react";
import { useWorkflowsApi } from "@/hooks/useApiWithFallback";
import { useWorkflowManagement } from "@/hooks/useWorkflowManagement";
import { type MockWorkflowStep } from "@/data/mock-data";
import {
  EmptyState,
  ToolIcon,
} from "@/components/ui";
import StepConfigPanel from "./step-config-panel";
import ToolsPalette from "./tools-palette";

interface WorkflowBuilderProps {
  workflowId: string | null;
}

export default function WorkflowBuilder({ workflowId }: WorkflowBuilderProps) {
  const [selectedStepIndex, setSelectedStepIndex] = useState<number | null>(null);
  const [workflowSteps, setWorkflowSteps] = useState<MockWorkflowStep[]>([]);
  const [workflowName, setWorkflowName] = useState("");
  const [workflowDescription] = useState(""); // setWorkflowDescription reserved for future use

  const { data: mockWorkflows = [] } = useWorkflowsApi();
  const { createWorkflow, updateWorkflow, executeWorkflow, deleteWorkflow } = useWorkflowManagement();

  // Load workflow data when workflowId changes
  const currentWorkflow = useMemo(() => {
    if (!workflowId || workflowId === "new") return null;
    return mockWorkflows.find(w => w.id === workflowId) || null;
  }, [workflowId, mockWorkflows]);

  // Update local state when workflow changes
  useEffect(() => {
    if (workflowId === "new") {
      setWorkflowSteps([]);
      setWorkflowName("New Workflow");
      setSelectedStepIndex(null);
    } else if (currentWorkflow) {
      setWorkflowSteps([...currentWorkflow.steps]);
      setWorkflowName(currentWorkflow.name);
      setSelectedStepIndex(null);
    }
  }, [workflowId, currentWorkflow]);

  const handleAddStep = (tool: string) => {
    const newStep: MockWorkflowStep = {
      name: `New ${tool} Step`,
      tool,
      description: `Configure this ${tool} step`,
    };
    setWorkflowSteps(prev => [...prev, newStep]);
  };

  const handleUpdateStep = (index: number, updatedStep: MockWorkflowStep) => {
    setWorkflowSteps(prev =>
      prev.map((step, i) => i === index ? updatedStep : step)
    );
  };

  const handleDeleteStep = (index: number) => {
    setWorkflowSteps(prev => prev.filter((_, i) => i !== index));
    if (selectedStepIndex === index) {
      setSelectedStepIndex(null);
    } else if (selectedStepIndex !== null && selectedStepIndex > index) {
      setSelectedStepIndex(selectedStepIndex - 1);
    }
  };

  const handleSaveWorkflow = async () => {
    try {
      const actions = workflowSteps.map((step, idx) => ({
        sequence: idx,
        tool: step.tool,
        action: step.name,
        inputs: (step as any).inputs || {},
        output: (step as any).output || `step_${idx}_output`,
      }));

      if (workflowId === "new") {
        // Create new workflow
        await createWorkflow.mutateAsync({
          name: workflowName,
          description: workflowDescription,
          actions,
        });
        console.log("Workflow created successfully");
      } else {
        // Update existing workflow
        await updateWorkflow.mutateAsync({
          id: workflowId!,
          name: workflowName,
          description: workflowDescription,
          actions,
        });
        console.log("Workflow updated successfully");
      }
    } catch (error) {
      console.error("Failed to save workflow:", error);
    }
  };

  const handleRunWorkflow = async () => {
    try {
      if (workflowId && workflowId !== "new") {
        // Execute workflow with test inputs
        const result = await executeWorkflow.mutateAsync({
          workflowId: workflowId,
          inputs: {}, // Could add UI for test inputs
        });
        console.log("Workflow execution result:", result);
      }
    } catch (error) {
      console.error("Failed to execute workflow:", error);
    }
  };

  const handleDeleteWorkflow = async () => {
    if (workflowId && workflowId !== "new") {
      const confirmed = confirm("Are you sure you want to delete this workflow?");
      if (confirmed) {
        try {
          await deleteWorkflow.mutateAsync(workflowId);
          console.log("Workflow deleted successfully");
        } catch (error) {
          console.error("Failed to delete workflow:", error);
        }
      }
    }
  };

  if (!workflowId) {
    return (
      <div className="h-full flex items-center justify-center">
        <EmptyState message="Select a workflow to edit or create a new one" />
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="border-b border-border p-4 bg-card rounded-t-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={workflowName}
              onChange={(e) => setWorkflowName(e.target.value)}
              className="text-lg font-semibold bg-transparent border-none outline-none focus:ring-2 focus:ring-primary rounded px-2 py-1"
            />
            <span className="text-sm text-muted-foreground">
              {workflowSteps.length} steps
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleSaveWorkflow}
              disabled={createWorkflow.isPending || updateWorkflow.isPending}
              className="flex items-center gap-2 px-3 py-1 text-sm bg-primary text-primary-foreground rounded hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              {createWorkflow.isPending || updateWorkflow.isPending ? 'Saving...' : 'Save'}
            </button>
            <button
              onClick={handleRunWorkflow}
              disabled={executeWorkflow.isPending || workflowId === "new"}
              className="flex items-center gap-2 px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition-colors disabled:opacity-50"
            >
              <Play className="w-4 h-4" />
              {executeWorkflow.isPending ? 'Running...' : 'Run'}
            </button>
            {workflowId !== "new" && (
              <button
                onClick={handleDeleteWorkflow}
                disabled={deleteWorkflow.isPending}
                className="flex items-center gap-2 px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                <Trash2 className="w-4 h-4" />
                {deleteWorkflow.isPending ? 'Deleting...' : 'Delete'}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Tools Palette */}
        <div className="w-64 border-r border-border p-4 bg-card">
          <ToolsPalette onAddStep={handleAddStep} />
        </div>

        {/* Center Panel - Workflow Steps */}
        <div className="flex-1 p-4 overflow-auto">
          {workflowSteps.length === 0 ? (
            <EmptyState message="Drag tools from the palette to build your workflow" />
          ) : (
            <div className="space-y-3">
              {workflowSteps.map((step, index) => (
                <div
                  key={index}
                  onClick={() => setSelectedStepIndex(index)}
                  className={`p-3 rounded-lg border cursor-pointer transition-all ${
                    selectedStepIndex === index
                      ? "border-primary bg-primary/5"
                      : "border-border bg-card hover:border-primary/50"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-xs font-medium">
                        {index + 1}
                      </div>
                      <ToolIcon tool={step.tool} className="w-5 h-5 text-muted-foreground" />
                      <div>
                        <div className="font-medium">{step.name}</div>
                        <div className="text-xs text-muted-foreground">{step.tool}</div>
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteStep(index);
                      }}
                      className="p-1 rounded hover:bg-destructive hover:text-destructive-foreground transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                  {step.description && (
                    <div className="mt-2 text-sm text-muted-foreground">
                      {step.description}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Panel - Step Configuration */}
        <div className="w-80 border-l border-border p-4 bg-card">
          <StepConfigPanel
            step={selectedStepIndex !== null ? workflowSteps[selectedStepIndex] : null}
            onUpdateStep={(updatedStep) => {
              if (selectedStepIndex !== null) {
                handleUpdateStep(selectedStepIndex, updatedStep);
              }
            }}
          />
        </div>
      </div>
    </div>
  );
}