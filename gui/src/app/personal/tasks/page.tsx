import { useState } from "react";
import { useTasks } from "@/hooks/useTasks";
import type { Task } from "@/types/task";
import { AddTaskForm } from "@/components/tasks/add-task-form";
import { TaskItem } from "@/components/tasks/task-item";
import { TaskCompletionModal } from "@/components/tasks/task-completion-modal";
import { EmptyState } from "@/components/ui/empty-state";
import { Separator } from "@/components/ui/separator";
import { CheckCircle2, Circle } from "lucide-react";

export default function TasksPage() {
  const { tasks, addTask, completeTask, updateTask } = useTasks();
  const [completingTask, setCompletingTask] = useState<Task | null>(null);

  const handleUseWorkflow = (taskTitle: string, workflowId: string) => {
    console.log("Executing workflow:", workflowId, "for task:", taskTitle);
    // TODO: Send to API to execute workflow
    // For now, just show a message
    alert(`Workflow ${workflowId} will be executed for: ${taskTitle}`);
  };

  const handleToggleTask = (task: Task) => {
    if (task.completed) {
      // Uncomplete the task
      updateTask(task.id, { completed: false, dateCompleted: undefined });
    } else {
      // Show completion modal
      setCompletingTask(task);
    }
  };

  const handleCompleteTask = (
    taskId: string,
    actualTime?: number,
    effortRating?: number,
    workflowUsed?: string,
    notes?: string
  ) => {
    completeTask(taskId, actualTime, effortRating, workflowUsed, notes);
  };

  const activeTasks = tasks.filter((t) => !t.completed);
  const completedTasks = tasks.filter((t) => t.completed);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Header */}
          <div>
            <h1 className="text-3xl font-bold">Tasks</h1>
            <p className="text-muted-foreground mt-1">
              Manage your to-do list with minimal friction
            </p>
          </div>

          {/* Add task form */}
          <AddTaskForm onAddTask={addTask} onUseWorkflow={handleUseWorkflow} />

          <Separator />

          {/* Active tasks */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Circle className="h-4 w-4 text-muted-foreground" />
              <h2 className="text-lg font-semibold">
                Active ({activeTasks.length})
              </h2>
            </div>
            {activeTasks.length === 0 ? (
              <EmptyState
                icon={Circle}
                title="No active tasks"
                description="Add a task above to get started"
              />
            ) : (
              <div className="space-y-2">
                {activeTasks.map((task) => (
                  <TaskItem
                    key={task.id}
                    task={task}
                    onToggle={handleToggleTask}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Completed tasks */}
          {completedTasks.length > 0 && (
            <>
              <Separator />
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
                  <h2 className="text-lg font-semibold">
                    Completed ({completedTasks.length})
                  </h2>
                </div>
                <div className="space-y-2">
                  {completedTasks.map((task) => (
                    <TaskItem
                      key={task.id}
                      task={task}
                      onToggle={handleToggleTask}
                    />
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Completion modal */}
      <TaskCompletionModal
        task={completingTask}
        open={!!completingTask}
        onClose={() => setCompletingTask(null)}
        onComplete={handleCompleteTask}
      />
    </div>
  );
}
