import { useMemo } from 'react';
import { useBackendQuery } from '@/lib/api';
import { mockInsights } from '@/data/mock-tasks';
import type { Task, Insight } from '@/types/task';

export function useTaskInsights(tasks: Task[]): Insight[] {
  // Try to fetch insights from backend API first
  const { data: apiInsights } = useBackendQuery<Insight[]>('/tasks/insights', {
    queryKey: ['task-insights'],
    fallbackData: mockInsights,
  });

  // Generate insights from local task data
  const generatedInsights = useGeneratedInsights(tasks);

  // Prefer API insights if available, otherwise use generated ones
  return apiInsights && apiInsights.length > 0 ? apiInsights : generatedInsights;
}

function useGeneratedInsights(tasks: Task[]): Insight[] {
  return useMemo(() => {
    const insights: Insight[] = [];
    const completedTasks = tasks.filter((t) => t.completed);

    if (completedTasks.length < 3) {
      return insights;
    }

    // Repetition detection
    const titleGroups = new Map<string, Task[]>();
    completedTasks.forEach((task) => {
      const normalizedTitle = task.title.toLowerCase().trim();
      const existing = titleGroups.get(normalizedTitle) || [];
      titleGroups.set(normalizedTitle, [...existing, task]);
    });

    // Find repeated tasks
    titleGroups.forEach((group, title) => {
      if (group.length >= 2) {
        insights.push({
          id: crypto.randomUUID(),
          type: 'repetition',
          title: 'Repeated Task Pattern',
          description: `You've completed "${group[0].title}" ${group.length} times. Consider creating a workflow or template for this task.`,
          relatedTasks: group.map((t) => t.id),
          dateCreated: new Date(),
        });
      }
    });

    // Bottleneck detection (high effort, long duration)
    const highEffortTasks = completedTasks.filter(
      (t) => t.effortRating && t.effortRating >= 4
    );
    if (highEffortTasks.length >= 3) {
      insights.push({
        id: crypto.randomUUID(),
        type: 'bottleneck',
        title: 'High Effort Tasks',
        description: `You have ${highEffortTasks.length} tasks with high effort ratings. These might benefit from breaking down into smaller steps or automating parts of the process.`,
        relatedTasks: highEffortTasks.map((t) => t.id),
        dateCreated: new Date(),
      });
    }

    // Optimization opportunities (tasks that took longer than estimated)
    const overEstimatedTasks = completedTasks.filter(
      (t) => t.estimatedTime && t.actualTime && t.actualTime > t.estimatedTime * 1.5
    );
    if (overEstimatedTasks.length >= 2) {
      const avgOverage = Math.round(
        overEstimatedTasks.reduce(
          (acc, t) => acc + ((t.actualTime || 0) - (t.estimatedTime || 0)),
          0
        ) / overEstimatedTasks.length
      );
      insights.push({
        id: crypto.randomUUID(),
        type: 'optimization',
        title: 'Time Estimation Improvement',
        description: `${overEstimatedTasks.length} tasks took significantly longer than estimated (avg. ${avgOverage}min over). Consider refining your estimates or identifying blockers.`,
        relatedTasks: overEstimatedTasks.map((t) => t.id),
        dateCreated: new Date(),
      });
    }

    // Tag-based insights
    const tagCounts = new Map<string, number>();
    completedTasks.forEach((task) => {
      task.tags.forEach((tag) => {
        tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1);
      });
    });

    const dominantTag = Array.from(tagCounts.entries()).sort(
      (a, b) => b[1] - a[1]
    )[0];

    if (dominantTag && dominantTag[1] >= 5) {
      insights.push({
        id: crypto.randomUUID(),
        type: 'optimization',
        title: `Focus Area: ${dominantTag[0]}`,
        description: `Most of your completed tasks (${dominantTag[1]}) are tagged as "${dominantTag[0]}". Consider creating dedicated workflows for this category.`,
        dateCreated: new Date(),
      });
    }

    return insights;
  }, [tasks]);
}
