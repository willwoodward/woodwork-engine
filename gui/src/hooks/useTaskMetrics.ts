import { useMemo } from 'react';
import type { Task, TaskMetrics } from '@/types/task';

export function useTaskMetrics(tasks: Task[]): TaskMetrics {
  return useMemo(() => {
    const completedTasks = tasks.filter((t) => t.completed);
    const totalTasks = tasks.length;

    // Completion rate
    const completionRate = totalTasks > 0
      ? Math.round((completedTasks.length / totalTasks) * 100)
      : 0;

    // Time saved (estimated vs actual)
    const timeSaved = completedTasks.reduce((acc, task) => {
      if (task.estimatedTime && task.actualTime) {
        return acc + (task.estimatedTime - task.actualTime);
      }
      return acc;
    }, 0);

    // Workflow adoption rate (tasks with workflow vs total completed)
    const tasksWithWorkflow = completedTasks.filter((t) => t.workflowUsed).length;
    const workflowAdoptionRate = completedTasks.length > 0
      ? Math.round((tasksWithWorkflow / completedTasks.length) * 100)
      : 0;

    // Repetition reduction (placeholder - would need more sophisticated logic)
    // For now, just a simple metric based on tasks with similar titles
    const titleGroups = new Map<string, number>();
    completedTasks.forEach((task) => {
      const normalizedTitle = task.title.toLowerCase().trim();
      titleGroups.set(normalizedTitle, (titleGroups.get(normalizedTitle) || 0) + 1);
    });
    const repeatedTasks = Array.from(titleGroups.values()).filter((count) => count > 1).length;
    const repetitionReduction = completedTasks.length > 0
      ? Math.max(0, 100 - Math.round((repeatedTasks / completedTasks.length) * 100))
      : 0;

    return {
      timeSaved,
      completionRate,
      repetitionReduction,
      workflowAdoptionRate,
    };
  }, [tasks]);
}
