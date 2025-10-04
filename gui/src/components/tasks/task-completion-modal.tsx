import { useState } from "react";
import type { Task } from "@/types/task";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";

interface TaskCompletionModalProps {
  task: Task | null;
  open: boolean;
  onClose: () => void;
  onComplete: (
    taskId: string,
    actualTime?: number,
    effortRating?: number,
    workflowUsed?: string,
    notes?: string
  ) => void;
}

export function TaskCompletionModal({
  task,
  open,
  onClose,
  onComplete,
}: TaskCompletionModalProps) {
  const [actualTime, setActualTime] = useState<string>("");
  const [effortRating, setEffortRating] = useState<number[]>([3]);
  const [workflowUsed, setWorkflowUsed] = useState("");
  const [notes, setNotes] = useState("");

  const handleSubmit = () => {
    if (!task) return;

    onComplete(
      task.id,
      actualTime ? parseInt(actualTime) : undefined,
      effortRating[0],
      workflowUsed || undefined,
      notes || undefined
    );

    // Reset form
    setActualTime("");
    setEffortRating([3]);
    setWorkflowUsed("");
    setNotes("");
    onClose();
  };

  const handleSkip = () => {
    if (!task) return;
    onComplete(task.id);
    onClose();
  };

  if (!task) return null;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Task Completed!</DialogTitle>
          <DialogDescription>
            Add some quick details about this task (optional)
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="actual-time">Actual time (minutes)</Label>
            <Input
              id="actual-time"
              type="number"
              placeholder={task.estimatedTime?.toString() || "30"}
              value={actualTime}
              onChange={(e) => setActualTime(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <div className="flex items-center justify-between">
              <Label>Effort rating</Label>
              <span className="text-sm text-muted-foreground">
                {effortRating[0]}/5
              </span>
            </div>
            <Slider
              value={effortRating}
              onValueChange={setEffortRating}
              min={1}
              max={5}
              step={1}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Easy</span>
              <span>Moderate</span>
              <span>Hard</span>
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="workflow">Workflow used</Label>
            <Input
              id="workflow"
              placeholder="e.g., Deep Work, Quick Task"
              value={workflowUsed}
              onChange={(e) => setWorkflowUsed(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea
              id="notes"
              placeholder="Any additional context..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={handleSkip}>
            Skip
          </Button>
          <Button onClick={handleSubmit}>Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
