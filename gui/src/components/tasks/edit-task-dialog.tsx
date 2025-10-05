import { useState, useEffect, useRef } from "react";
import type { Task, TaskPriority, TaskTag } from "@/types/task";
import { useTags } from "@/hooks/useTags";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { X, Plus } from "lucide-react";

interface EditTaskDialogProps {
  task: Task;
  open: boolean;
  onClose: () => void;
  onSave: (taskId: string, updates: Partial<Task>) => void;
}

export function EditTaskDialog({ task, open, onClose, onSave }: EditTaskDialogProps) {
  const [title, setTitle] = useState(task.title);
  const [selectedTags, setSelectedTags] = useState<TaskTag[]>(task.tags);
  const [estimatedTime, setEstimatedTime] = useState(task.estimatedTime?.toString() || "");
  const [actualTime, setActualTime] = useState(task.actualTime?.toString() || "");
  const [priority, setPriority] = useState<TaskPriority>(task.priority);
  const [notes, setNotes] = useState(task.notes || "");
  const [effortRating, setEffortRating] = useState(task.effortRating?.toString() || "");
  const [newTagInput, setNewTagInput] = useState("");
  const newTagInputRef = useRef<HTMLInputElement>(null);
  const { tags: availableTags, addTag } = useTags();

  // Reset form when task changes
  useEffect(() => {
    setTitle(task.title);
    setSelectedTags(task.tags);
    setEstimatedTime(task.estimatedTime?.toString() || "");
    setActualTime(task.actualTime?.toString() || "");
    setPriority(task.priority);
    setNotes(task.notes || "");
    setEffortRating(task.effortRating?.toString() || "");
  }, [task]);

  const handleSave = () => {
    onSave(task.id, {
      title,
      tags: selectedTags,
      estimatedTime: estimatedTime ? parseInt(estimatedTime) : undefined,
      actualTime: actualTime ? parseInt(actualTime) : undefined,
      priority,
      notes: notes || undefined,
      effortRating: effortRating ? parseInt(effortRating) : undefined,
    });
    onClose();
  };

  const toggleTag = (tag: TaskTag) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
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
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Edit Task</DialogTitle>
          <DialogDescription>
            Update task details and metadata
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Title */}
          <div className="space-y-2">
            <Label htmlFor="title">Task Title</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="What needs to be done?"
            />
          </div>

          {/* Tags */}
          <div className="space-y-2">
            <Label>Tags</Label>
            <div className="flex flex-wrap gap-2">
              {availableTags.map((tag) => (
                <Badge
                  key={tag}
                  variant={selectedTags.includes(tag) ? "default" : "outline"}
                  className="cursor-pointer"
                  onClick={() => toggleTag(tag)}
                >
                  {tag}
                  {selectedTags.includes(tag) && (
                    <X className="h-3 w-3 ml-1" />
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
            </div>
          </div>

          {/* Time estimates */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="estimatedTime">Estimated Time (min)</Label>
              <Input
                id="estimatedTime"
                type="number"
                value={estimatedTime}
                onChange={(e) => setEstimatedTime(e.target.value)}
                placeholder="30"
              />
            </div>
            {task.completed && (
              <div className="space-y-2">
                <Label htmlFor="actualTime">Actual Time (min)</Label>
                <Input
                  id="actualTime"
                  type="number"
                  value={actualTime}
                  onChange={(e) => setActualTime(e.target.value)}
                  placeholder="45"
                />
              </div>
            )}
          </div>

          {/* Priority and Effort */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="priority">Priority</Label>
              <Select value={priority} onValueChange={(value: TaskPriority) => setPriority(value)}>
                <SelectTrigger id="priority">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {task.completed && (
              <div className="space-y-2">
                <Label htmlFor="effort">Effort Rating (1-5)</Label>
                <Input
                  id="effort"
                  type="number"
                  min="1"
                  max="5"
                  value={effortRating}
                  onChange={(e) => setEffortRating(e.target.value)}
                  placeholder="3"
                />
              </div>
            )}
          </div>

          {/* Notes */}
          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea
              id="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add any notes or context..."
              rows={3}
            />
          </div>

          {/* Workflow indicator */}
          {task.workflowUsed && (
            <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20">
              <p className="text-sm text-green-600">
                <strong>Workflow:</strong> {task.workflowUsed}
              </p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>Save Changes</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
