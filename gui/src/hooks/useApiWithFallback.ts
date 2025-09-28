import { useQuery } from "@tanstack/react-query";
import { mockWorkflows, mockChatSessions, type MockWorkflow, type MockChatSession } from "@/data/mock-data";

interface ApiConfig<T> {
  queryKey: string[];
  endpoint: string;
  fallbackData: T;
  queryOptions?: any;
}

/**
 * Generic hook for API calls with automatic fallback to mock data
 * Falls back to mock data if API call fails
 */
export function useApiWithFallback<T>({
  queryKey,
  endpoint,
  fallbackData,
  queryOptions = {},
}: ApiConfig<T>) {
  return useQuery<T, Error>({
    queryKey,
    queryFn: async (): Promise<T> => {
      try {
        const response = await fetch(endpoint);

        if (!response.ok) {
          console.warn(`API call failed (${response.status}), using fallback data for ${endpoint}`);
          return fallbackData;
        }

        const data = await response.json();
        return data;
      } catch (error) {
        console.warn(`API call failed with error, using fallback data for ${endpoint}:`, error);
        return fallbackData;
      }
    },
    // Default options that prioritize showing data quickly
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 1, // Only retry once before falling back
    ...queryOptions,
  });
}

/**
 * Hook specifically for workflows API with fallback
 */
export function useWorkflowsApi() {
  return useApiWithFallback<MockWorkflow[]>({
    queryKey: ["workflows"],
    endpoint: "/api/workflows/get",
    fallbackData: mockWorkflows,
  });
}

/**
 * Hook for chat sessions API with fallback
 */
export function useChatSessionsApi() {
  return useApiWithFallback<MockChatSession[]>({
    queryKey: ["chat-sessions"],
    endpoint: "/api/chat/sessions",
    fallbackData: mockChatSessions,
  });
}

/**
 * Hook for individual chat session API with fallback
 */
export function useChatSessionApi(sessionId: string) {
  const fallbackSession = mockChatSessions.find(s => s.id === sessionId) || mockChatSessions[0];

  return useApiWithFallback<MockChatSession>({
    queryKey: ["chat-session", sessionId],
    endpoint: `/api/chat/sessions/${sessionId}`,
    fallbackData: fallbackSession,
  });
}