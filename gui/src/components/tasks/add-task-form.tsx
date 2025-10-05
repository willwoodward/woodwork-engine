import { useState, useRef } from "react";
import type { TaskPriority, TaskTag } from "@/types/task";
import { useWorkflowMatch, type WorkflowMatchResponse } from "@/hooks/useWorkflowMatch";
import { useTags } from "@/hooks/useTags";
import { WorkflowMatchDialog } from "./workflow-match-dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Sparkles, WifiOff, X } from "lucide-react";

interface AddTaskFormProps {
  onAddTask: (
    title: string,
    tags: TaskTag[],
    estimatedTime?: number,
    priority?: TaskPriority,
    notes?: string
  ) => void;
  onUseWorkflow?: (taskTitle: string, workflowId: string) => void;
  onTagClick?: (tag: string) => void;
  onTagDelete?: (tag: string) => void;
  activeFilterTags?: TaskTag[];
}

export function AddTaskForm({ onAddTask, onUseWorkflow, onTagClick, onTagDelete, activeFilterTags = [] }: AddTaskFormProps) {
  const [title, setTitle] = useState("");
  const [selectedTags, setSelectedTags] = useState<TaskTag[]>([]);
  const [estimatedTime, setEstimatedTime] = useState("");
  const [priority, setPriority] = useState<TaskPriority>("medium");
  const [notes, setNotes] = useState("");
  const [showOptions, setShowOptions] = useState(false);
  const [newTagInput, setNewTagInput] = useState("");
  const newTagInputRef = useRef<HTMLInputElement>(null);

  // Workflow matching state
  const [showWorkflowDialog, setShowWorkflowDialog] = useState(false);
  const [matchResult, setMatchResult] = useState<WorkflowMatchResponse | null>(null);
  const [lastTaskTitle, setLastTaskTitle] = useState<string>("");
  const [agentUnavailable, setAgentUnavailable] = useState(false);
  const workflowMatch = useWorkflowMatch();
  const { tags: availableTags, addTag } = useTags();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    // Save form values before resetting
    const taskData = {
      title,
      tags: selectedTags,
      estimatedTime: estimatedTime ? parseInt(estimatedTime) : undefined,
      priority,
      notes: notes.trim() || undefined,
    };

    // OPTIMISTIC: Add task immediately (instant UI update)
    onAddTask(
      taskData.title,
      taskData.tags,
      taskData.estimatedTime,
      taskData.priority,
      taskData.notes
    );

    // Save title for workflow dialog
    setLastTaskTitle(taskData.title);

    // Reset form immediately for next task
    resetForm();

    // BACKGROUND: Check for workflow match (non-blocking)
    workflowMatch.mutate(
      {
        taskTitle: taskData.title,
        tags: taskData.tags,
      },
      {
        onSuccess: (result) => {
          setAgentUnavailable(false);
          setMatchResult(result);
          if (result.canUseWorkflow) {
            // Show dialog suggesting workflow - task already added
            setShowWorkflowDialog(true);
          }
          // If no match, task is already added - nothing to do
        },
        onError: (error) => {
          // Show brief indicator that agent is unavailable
          if (error.message?.includes('Failed to fetch') ||
              error.message?.includes('ERR_CONNECTION_REFUSED')) {
            setAgentUnavailable(true);
            setTimeout(() => setAgentUnavailable(false), 3000);
          }
          // Task is already added - nothing to do
        },
      }
    );
  };

  const addTaskManually = () => {
    // This is now only called from the workflow dialog
    // when user chooses "Add Manually" instead of using workflow
    resetForm();
    setShowWorkflowDialog(false);
  };

  const handleUseWorkflow = () => {
    if (matchResult?.workflowId && onUseWorkflow) {
      onUseWorkflow(lastTaskTitle, matchResult.workflowId);
      setShowWorkflowDialog(false);
    }
  };

  const resetForm = () => {
    setTitle("");
    setSelectedTags([]);
    setEstimatedTime("");
    setPriority("medium");
    setNotes("");
    setShowOptions(false);
    setMatchResult(null);
  };


  const handleAddNewTag = (e: React.FormEvent) => {
    e.preventDefault();
    const tag = newTagInput.trim().toLowerCase();
    if (!tag) return;

    // Add to available tags if not already present
    if (!availableTags.includes(tag)) {
      addTag(tag);
    }

    // Add to selected tags if not already selected
    if (!selectedTags.includes(tag)) {
      setSelectedTags((prev) => [...prev, tag]);
    }

    setNewTagInput("");
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

        {/* Tag selection */}
        <div className="flex items-center gap-2 flex-wrap">
          {availableTags.map((tag) => (
            <Badge
              key={tag}
              variant={activeFilterTags.includes(tag) ? "default" : "outline"}
              className="cursor-pointer group pr-0 group-hover:pr-1"
            >
              <span onClick={() => onTagClick?.(tag)}>{tag}</span>
              {onTagDelete && (
                <X
                  className="h-3 w-3 ml-0 group-hover:ml-1 w-0 group-hover:w-3 opacity-0 group-hover:opacity-100 transition-all inline-block"
                  onClick={(e) => {
                    e.stopPropagation();
                    onTagDelete(tag);
                  }}
                />
              )}
            </Badge>
          ))}
          <div className="flex items-center gap-1">
            <Input
              ref={newTagInputRef}
              type="text"
              placeholder="+ new tag"
              value={newTagInput}
              onChange={(e) => setNewTagInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleAddNewTag(e);
                }
              }}
              className="h-7 w-24 text-xs"
            />
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 px-2"
              onClick={(e) => {
                e.preventDefault();
                handleAddNewTag(e);
              }}
            >
              <Plus className="h-3 w-3" />
            </Button>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setShowOptions(!showOptions)}
            className="text-xs"
          >
            {showOptions ? "Less" : "More"} options
          </Button>

          {/* Agent unavailable indicator */}
          {agentUnavailable && (
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground ml-auto">
              <WifiOff className="h-3 w-3" />
              <span>AI offline - task added manually</span>
            </div>
          )}
        </div>

        {/* Optional metadata */}
        {showOptions && (
          <div className="space-y-3 p-3 rounded-lg border bg-card">
            <div className="grid grid-cols-2 gap-3">
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
            <div className="space-y-2">
              <label className="text-xs font-medium">Notes</label>
              <Textarea
                placeholder="Add any notes or details..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="resize-none"
                rows={3}
              />
            </div>
          </div>
        )}
      </form>

      {/* Workflow Match Dialog */}
      <WorkflowMatchDialog
        open={showWorkflowDialog}
        onClose={() => setShowWorkflowDialog(false)}
        matchResult={matchResult}
        taskTitle={lastTaskTitle}
        onUseWorkflow={handleUseWorkflow}
        onAddManually={addTaskManually}
        isLoading={workflowMatch.isPending}
      />
    </>
  );
}
