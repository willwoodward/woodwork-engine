import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Workflow, Sparkles, ArrowRight, Network } from "lucide-react";
import type { WorkflowMatchResponse } from "@/hooks/useWorkflowMatch";
import { WorkflowGraphPreview, type WorkflowGraphData } from "@/components/workflows/workflow-graph";

interface WorkflowMatchDialogProps {
  open: boolean;
  onClose: () => void;
  matchResult: WorkflowMatchResponse | null;
  taskTitle: string;
  onUseWorkflow: () => void;
  onAddManually: () => void;
  isLoading?: boolean;
}

export function WorkflowMatchDialog({
  open,
  onClose,
  matchResult,
  taskTitle,
  onUseWorkflow,
  onAddManually,
  isLoading,
}: WorkflowMatchDialogProps) {
  const [activeTab, setActiveTab] = useState("actions");

  if (isLoading) {
    return (
      <Dialog open={open} onOpenChange={onClose}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 animate-pulse text-purple-500" />
              Checking for workflows...
            </DialogTitle>
          </DialogHeader>
          <div className="py-6 text-center">
            <p className="text-sm text-muted-foreground">
              Analyzing task to find matching workflows
            </p>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  if (!matchResult) return null;

  const { canUseWorkflow, workflowName, confidence, actions, graph, message } =
    matchResult;

  // Debug: Log graph data
  console.log('WorkflowMatchDialog - Graph data:', graph);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[700px] max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Workflow className="h-5 w-5 text-purple-500" />
            Workflow Match Found
          </DialogTitle>
          <DialogDescription>
            AI found a workflow that can help with: <strong>{taskTitle}</strong>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {canUseWorkflow && workflowName ? (
            <>
              <div className="p-4 rounded-lg bg-purple-500/10 border border-purple-500/20">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold text-lg">{workflowName}</h3>
                  {confidence && (
                    <Badge variant="outline" className="bg-green-500/10 text-green-500 border-green-500/20">
                      {Math.round(confidence * 100)}% match
                    </Badge>
                  )}
                </div>
                {message && (
                  <p className="text-sm text-muted-foreground">{message}</p>
                )}
              </div>

              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="actions" className="gap-2">
                    <Sparkles className="h-4 w-4" />
                    Actions
                  </TabsTrigger>
                  <TabsTrigger value="graph" className="gap-2" disabled={!graph}>
                    <Network className="h-4 w-4" />
                    Graph View
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="actions" className="space-y-4 mt-4">
                  {actions && actions.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-sm font-medium">Suggested Actions:</p>
                      <div className="space-y-2 max-h-[300px] overflow-y-auto">
                        {actions.map((action, index) => (
                          <div
                            key={action.id}
                            className="flex items-start gap-2 text-sm p-2 rounded bg-muted/50"
                          >
                            <span className="font-semibold text-muted-foreground min-w-[20px]">
                              {index + 1}.
                            </span>
                            <div>
                              <p className="font-medium">{action.name}</p>
                              {action.description && (
                                <p className="text-xs text-muted-foreground">
                                  {action.description}
                                </p>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex items-center gap-2 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                    <Sparkles className="h-4 w-4 text-blue-500" />
                    <p className="text-sm text-blue-500">
                      The AI can execute this workflow for you automatically
                    </p>
                  </div>
                </TabsContent>

                <TabsContent value="graph" className="mt-4">
                  {graph ? (
                    <div className="rounded-lg bg-muted/50 border border-border" style={{ height: '400px' }}>
                      <WorkflowGraphPreview graph={graph} className="w-full h-full" />
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-[400px] text-muted-foreground">
                      No graph data available for this workflow
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            </>
          ) : (
            <div className="p-4 rounded-lg bg-muted/50 border border-border">
              <p className="text-sm text-muted-foreground">
                {message ||
                  "No matching workflow found. You can add this as a manual task."}
              </p>
            </div>
          )}
        </div>

        <DialogFooter className="gap-2">
          {canUseWorkflow ? (
            <>
              <Button variant="outline" onClick={onAddManually}>
                Add Manually
              </Button>
              <Button onClick={onUseWorkflow} className="gap-2">
                <Workflow className="h-4 w-4" />
                Use Workflow
                <ArrowRight className="h-4 w-4" />
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button onClick={onAddManually}>Add as Task</Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
