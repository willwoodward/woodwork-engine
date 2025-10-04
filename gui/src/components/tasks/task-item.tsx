import type { Task } from "@/types/task";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Clock } from "lucide-react";
import { cn } from "@/lib/utils";

interface TaskItemProps {
  task: Task;
  onToggle: (task: Task) => void;
}

export function TaskItem({ task, onToggle }: TaskItemProps) {
  const priorityColors = {
    low: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    medium: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
    high: "bg-red-500/10 text-red-500 border-red-500/20",
  };

  return (
    <div
      className={cn(
        "flex items-start gap-3 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors",
        task.completed && "opacity-60"
      )}
    >
      <Checkbox
        checked={task.completed}
        onCheckedChange={() => onToggle(task)}
        className="mt-1"
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <p
            className={cn(
              "text-sm font-medium",
              task.completed && "line-through text-muted-foreground"
            )}
          >
            {task.title}
          </p>
          {task.priority !== "medium" && (
            <Badge
              variant="outline"
              className={cn("text-xs", priorityColors[task.priority])}
            >
              {task.priority}
            </Badge>
          )}
        </div>
        {(task.tags.length > 0 || task.estimatedTime) && (
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            {task.tags.map((tag) => (
              <Badge key={tag} variant="secondary" className="text-xs">
                {tag}
              </Badge>
            ))}
            {task.estimatedTime && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />
                <span>{task.estimatedTime}m</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
