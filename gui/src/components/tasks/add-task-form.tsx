import { useState } from "react";
import type { TaskPriority, TaskTag } from "@/types/task";
import { useWorkflowMatch, type WorkflowMatchResponse } from "@/hooks/useWorkflowMatch";
import { WorkflowMatchDialog } from "./workflow-match-dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface AddTaskFormProps {
  onAddTask: (
    title: string,
    tags: TaskTag[],
    estimatedTime?: number,
    priority?: TaskPriority
  ) => void;
  onUseWorkflow?: (taskTitle: string, workflowId: string) => void;
}

const commonTags: TaskTag[] = ["work", "personal", "admin"];

export function AddTaskForm({ onAddTask, onUseWorkflow }: AddTaskFormProps) {
  const [title, setTitle] = useState("");
  const [selectedTags, setSelectedTags] = useState<TaskTag[]>([]);
  const [estimatedTime, setEstimatedTime] = useState("");
  const [priority, setPriority] = useState<TaskPriority>("medium");
  const [showOptions, setShowOptions] = useState(false);

  // Workflow matching state
  const [showWorkflowDialog, setShowWorkflowDialog] = useState(false);
  const [matchResult, setMatchResult] = useState<WorkflowMatchResponse | null>(null);
  const workflowMatch = useWorkflowMatch();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    // Check for workflow match
    workflowMatch.mutate(
      {
        taskTitle: title,
        tags: selectedTags,
      },
      {
        onSuccess: (result) => {
          setMatchResult(result);
          if (result.canUseWorkflow) {
            setShowWorkflowDialog(true);
          } else {
            // No workflow match, add as regular task
            addTaskManually();
          }
        },
        onError: () => {
          // If workflow matching fails, just add the task normally
          addTaskManually();
        },
      }
    );
  };

  const addTaskManually = () => {
    onAddTask(
      title,
      selectedTags,
      estimatedTime ? parseInt(estimatedTime) : undefined,
      priority
    );
    resetForm();
    setShowWorkflowDialog(false);
  };

  const handleUseWorkflow = () => {
    if (matchResult?.workflowId && onUseWorkflow) {
      onUseWorkflow(title, matchResult.workflowId);
      resetForm();
      setShowWorkflowDialog(false);
    }
  };

  const resetForm = () => {
    setTitle("");
    setSelectedTags([]);
    setEstimatedTime("");
    setPriority("medium");
    setShowOptions(false);
    setMatchResult(null);
  };

  const toggleTag = (tag: TaskTag) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  return (
    <>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="flex gap-2">
          <Input
            placeholder="Add a task..."
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="flex-1"
            disabled={workflowMatch.isPending}
          />
          <Button type="submit" size="icon" disabled={workflowMatch.isPending}>
            {workflowMatch.isPending ? (
              <Sparkles className="h-4 w-4 animate-pulse" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
          </Button>
        </div>

        {/* Quick tag selection */}
        <div className="flex items-center gap-2 flex-wrap">
          {commonTags.map((tag) => (
            <Badge
              key={tag}
              variant={selectedTags.includes(tag) ? "default" : "outline"}
              className="cursor-pointer"
              onClick={() => toggleTag(tag)}
            >
              {tag}
            </Badge>
          ))}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setShowOptions(!showOptions)}
            className="text-xs"
          >
            {showOptions ? "Less" : "More"} options
          </Button>
        </div>

        {/* Optional metadata */}
        {showOptions && (
          <div className="grid grid-cols-2 gap-3 p-3 rounded-lg border bg-card">
            <div className="space-y-2">
              <label className="text-xs font-medium">Estimated time (min)</label>
              <Input
                type="number"
                placeholder="30"
                value={estimatedTime}
                onChange={(e) => setEstimatedTime(e.target.value)}
                className="h-8"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium">Priority</label>
              <Select value={priority} onValueChange={(v) => setPriority(v as TaskPriority)}>
                <SelectTrigger className="h-8">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        )}
      </form>

      {/* Workflow Match Dialog */}
      <WorkflowMatchDialog
        open={showWorkflowDialog}
        onClose={() => setShowWorkflowDialog(false)}
        matchResult={matchResult}
        taskTitle={title}
        onUseWorkflow={handleUseWorkflow}
        onAddManually={addTaskManually}
        isLoading={workflowMatch.isPending}
      />
    </>
  );
}
