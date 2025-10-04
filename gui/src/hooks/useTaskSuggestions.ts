import { useBackendQuery } from '@/lib/api';
import { mockSuggestions } from '@/data/mock-tasks';
import type { Suggestion } from '@/types/task';

export function useTaskSuggestions() {
  const { data: suggestions, isLoading, error } = useBackendQuery<Suggestion[]>(
    '/tasks/suggestions',
    {
      queryKey: ['task-suggestions'],
      fallbackData: mockSuggestions,
    }
  );

  return {
    suggestions: suggestions || [],
    isLoading,
    error,
  };
}
