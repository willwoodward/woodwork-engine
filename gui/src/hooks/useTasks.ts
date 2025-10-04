import { useState, useEffect } from 'react';
import { useBackendQuery } from '@/lib/api';
import { mockTasks } from '@/data/mock-tasks';
import type { Task, TaskPriority, TaskTag } from '@/types/task';

const STORAGE_KEY = 'woodwork-tasks';

export function useTasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isInitialized, setIsInitialized] = useState(false);

  // Fetch tasks from backend API with fallback to mock data
  const { data: apiTasks } = useBackendQuery<Task[]>('/tasks', {
    queryKey: ['tasks'],
    fallbackData: mockTasks,
  });

  // Load tasks from localStorage on mount, or use API/mock data
  useEffect(() => {
    if (isInitialized || !apiTasks) return;

    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && stored !== '[]') {
      // Only use localStorage if it has actual data
      try {
        const parsed = JSON.parse(stored);
        if (parsed && parsed.length > 0) {
          // Convert date strings back to Date objects
          const tasksWithDates = parsed.map((task: any) => ({
            ...task,
            dateCreated: new Date(task.dateCreated),
            dateCompleted: task.dateCompleted ? new Date(task.dateCompleted) : undefined,
          }));
          setTasks(tasksWithDates);
          setIsInitialized(true);
          return;
        }
      } catch (e) {
        console.error('Failed to parse tasks from localStorage', e);
      }
    }

    // No localStorage data or it's empty, use API/mock data
    setTasks(apiTasks);
    setIsInitialized(true);
  }, [apiTasks, isInitialized]);

  // Save tasks to localStorage whenever they change
  useEffect(() => {
    if (isInitialized) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
    }
  }, [tasks, isInitialized]);

  const addTask = (
    title: string,
    tags: TaskTag[] = [],
    estimatedTime?: number,
    priority: TaskPriority = 'medium'
  ) => {
    const newTask: Task = {
      id: crypto.randomUUID(),
      title,
      tags,
      estimatedTime,
      priority,
      dateCreated: new Date(),
      completed: false,
    };
    setTasks((prev) => [newTask, ...prev]);
    return newTask;
  };

  const updateTask = (id: string, updates: Partial<Task>) => {
    setTasks((prev) =>
      prev.map((task) => (task.id === id ? { ...task, ...updates } : task))
    );
  };

  const completeTask = (
    id: string,
    actualTime?: number,
    effortRating?: number,
    workflowUsed?: string,
    notes?: string
  ) => {
    setTasks((prev) =>
      prev.map((task) =>
        task.id === id
          ? {
              ...task,
              completed: true,
              dateCompleted: new Date(),
              actualTime,
              effortRating,
              workflowUsed,
              notes,
            }
          : task
      )
    );
  };

  const deleteTask = (id: string) => {
    setTasks((prev) => prev.filter((task) => task.id !== id));
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
  };
}
