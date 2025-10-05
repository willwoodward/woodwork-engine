import { useBackendQuery, useBackendMutation } from '@/lib/api';
import { useQueryClient } from '@tanstack/react-query';
import { mockTasks } from '@/data/mock-tasks';
import type { Task, TaskPriority, TaskTag } from '@/types/task';

const QUERY_KEY = ['tasks'];

export function useTasks() {
  const queryClient = useQueryClient();

  // Fetch tasks from backend API with fallback to mock data
  const { data: tasks = [] } = useBackendQuery<Task[]>('/tasks', {
    queryKey: QUERY_KEY,
    fallbackData: mockTasks,
  });

  // Create task mutation with optimistic update
  const createMutation = useBackendMutation<Task, Partial<Task>>('/tasks', {
    method: 'POST',
    onMutate: async (newTask) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: QUERY_KEY });

      // Snapshot previous value
      const previousTasks = queryClient.getQueryData<Task[]>(QUERY_KEY);

      // Optimistically update to the new value
      queryClient.setQueryData<Task[]>(QUERY_KEY, (old = []) => [
        newTask as Task,
        ...old,
      ]);

      return { previousTasks };
    },
    onError: (_err, _newTask, context) => {
      // Rollback on error
      if (context?.previousTasks) {
        queryClient.setQueryData(QUERY_KEY, context.previousTasks);
      }
    },
    onSettled: () => {
      // Refetch after mutation
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });

  // Update task mutation with optimistic update
  const updateMutation = useBackendMutation<Task, { id: string } & Partial<Task>>(
    '/tasks/:id',
    {
      method: 'PATCH',
      onMutate: async (updates) => {
        await queryClient.cancelQueries({ queryKey: QUERY_KEY });
        const previousTasks = queryClient.getQueryData<Task[]>(QUERY_KEY);

        queryClient.setQueryData<Task[]>(QUERY_KEY, (old = []) =>
          old.map((task) =>
            task.id === updates.id ? { ...task, ...updates } : task
          )
        );

        return { previousTasks };
      },
      onError: (_err, _updates, context) => {
        if (context?.previousTasks) {
          queryClient.setQueryData(QUERY_KEY, context.previousTasks);
        }
      },
      onSettled: () => {
        queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      },
    }
  );

  // Delete task mutation with optimistic update
  const deleteMutation = useBackendMutation<void, { id: string }>('/tasks/:id', {
    method: 'DELETE',
    onMutate: async (variables) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEY });
      const previousTasks = queryClient.getQueryData<Task[]>(QUERY_KEY);

      queryClient.setQueryData<Task[]>(QUERY_KEY, (old = []) =>
        old.filter((task) => task.id !== variables.id)
      );

      return { previousTasks };
    },
    onError: (_err, _variables, context) => {
      if (context?.previousTasks) {
        queryClient.setQueryData(QUERY_KEY, context.previousTasks);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });

  const addTask = (
    title: string,
    tags: TaskTag[] = [],
    estimatedTime?: number,
    priority: TaskPriority = 'medium',
    notes?: string
  ) => {
    const newTask: Task = {
      id: crypto.randomUUID(),
      title,
      tags,
      estimatedTime,
      priority,
      notes,
      dateCreated: new Date(),
      completed: false,
    };
    createMutation.mutate(newTask);
    return newTask;
  };

  const updateTask = (id: string, updates: Partial<Task>) => {
    updateMutation.mutate({ id, ...updates });
  };

  const completeTask = (
    id: string,
    actualTime?: number,
    effortRating?: number,
    workflowUsed?: string,
    notes?: string
  ) => {
    updateMutation.mutate({
      id,
      completed: true,
      dateCompleted: new Date(),
      actualTime,
      effortRating,
      workflowUsed,
      notes,
    });
  };

  const deleteTask = (id: string) => {
    deleteMutation.mutate({ id });
  };

  const toggleComplete = (id: string) => {
    const task = tasks.find((t) => t.id === id);
    if (task) {
      if (task.completed) {
        // Uncomplete the task
        updateTask(id, { completed: false, dateCompleted: undefined });
      } else {
        // Mark as complete without additional data (will trigger modal in UI)
        return task;
      }
    }
  };

  return {
    tasks,
    addTask,
    updateTask,
    completeTask,
    deleteTask,
    toggleComplete,
    isLoading: createMutation.isPending || updateMutation.isPending || deleteMutation.isPending,
  };
}
