import { useState, useEffect } from "react";
import type { Task } from "@/types/task";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Clock, Trash2, Sparkles, Edit } from "lucide-react";
import { cn } from "@/lib/utils";
import { useWorkflowMatch } from "@/hooks/useWorkflowMatch";
import { WorkflowMatchDialog } from "./workflow-match-dialog";
import { EditTaskDialog } from "./edit-task-dialog";

interface TaskItemProps {
  task: Task;
  onToggle: (task: Task) => void;
  onDelete?: (taskId: string) => void;
  onEdit?: (taskId: string, updates: Partial<Task>) => void;
  onTagClick?: (tag: string) => void;
}

export function TaskItem({ task, onToggle, onDelete, onEdit, onTagClick }: TaskItemProps) {
  const [showWorkflowDialog, setShowWorkflowDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [workflowMatch, setWorkflowMatch] = useState<any>(null);
  const workflowMatchMutation = useWorkflowMatch();

  const priorityColors = {
    low: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    medium: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
    high: "bg-red-500/10 text-red-500 border-red-500/20",
  };

  // Check if task could have a workflow suggestion (only for non-completed tasks)
  const shouldShowWorkflowButton = !task.completed && !task.workflowUsed;

  // Auto-check for workflow on mount for tasks that should show suggestion
  useEffect(() => {
    if (shouldShowWorkflowButton && !workflowMatch) {
      workflowMatchMutation.mutate(
        {
          taskTitle: task.title,
          tags: task.tags,
        },
        {
          onSuccess: (result) => {
            setWorkflowMatch(result);
          },
        }
      );
    }
  }, []); // Only run once on mount

  const handleViewWorkflow = () => {
    if (workflowMatch?.canUseWorkflow) {
      setShowWorkflowDialog(true);
    }
  };

  const handleApproveWorkflow = () => {
    // TODO: Save workflow to task
    console.log("Workflow approved for task:", task.id);
    setShowWorkflowDialog(false);
  };

  return (
    <>
      <div
        className={cn(
          "group flex items-start gap-3 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors",
          task.completed && "opacity-60"
        )}
      >
        <Checkbox
          checked={task.completed}
          onCheckedChange={() => onToggle(task)}
          className="mt-0.5"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2 flex-wrap">
              <p
                className={cn(
                  "text-sm font-medium",
                  task.completed && "line-through text-muted-foreground"
                )}
              >
                {task.title}
              </p>

              {/* Tags inline */}
              {task.tags.map((tag) => (
                <Badge
                  key={tag}
                  variant="secondary"
                  className="text-xs cursor-pointer hover:bg-secondary/80"
                  onClick={(e) => {
                    e.stopPropagation();
                    onTagClick?.(tag);
                  }}
                >
                  {tag}
                </Badge>
              ))}

              {/* Time inline */}
              {task.estimatedTime && (
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  <span>{task.estimatedTime}m</span>
                </div>
              )}

              {/* Workflow badge if already using one */}
              {task.workflowUsed && (
                <Badge variant="outline" className="text-xs bg-green-500/10 text-green-600 border-green-500/20">
                  <Sparkles className="h-3 w-3 mr-1" />
                  {task.workflowUsed}
                </Badge>
              )}

              {/* Workflow suggestion badge - auto-shown if match found */}
              {shouldShowWorkflowButton && workflowMatch?.canUseWorkflow && (
                <Button
                  variant="outline"
                  size="sm"
                  className="h-6 text-xs gap-1 bg-purple-500/5 border-purple-500/20 text-purple-600 hover:bg-purple-500/10 px-2"
                  onClick={handleViewWorkflow}
                >
                  <Sparkles className="h-3 w-3" />
                  {Math.round((workflowMatch.confidence || 0) * 100)}% match
                </Button>
              )}
            </div>

            <div className="flex items-center gap-1 flex-shrink-0">
              {task.priority !== "medium" && (
                <Badge
                  variant="outline"
                  className={cn("text-xs", priorityColors[task.priority])}
                >
                  {task.priority}
                </Badge>
              )}
              {onEdit && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={() => setShowEditDialog(true)}
                >
                  <Edit className="h-3.5 w-3.5 text-muted-foreground hover:text-primary" />
                </Button>
              )}
              {onDelete && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={() => onDelete(task.id)}
                >
                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" />
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Workflow Match Dialog */}
      {workflowMatch && (
        <WorkflowMatchDialog
          open={showWorkflowDialog}
          onClose={() => setShowWorkflowDialog(false)}
          matchResult={workflowMatch}
          taskTitle={task.title}
          onUseWorkflow={handleApproveWorkflow}
          onAddManually={() => setShowWorkflowDialog(false)}
        />
      )}

      {/* Edit Task Dialog */}
      {onEdit && (
        <EditTaskDialog
          task={task}
          open={showEditDialog}
          onClose={() => setShowEditDialog(false)}
          onSave={onEdit}
        />
      )}
    </>
  );
}
