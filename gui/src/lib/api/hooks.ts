import { useQuery, useMutation, type UseQueryOptions, type UseMutationOptions } from '@tanstack/react-query';
import { api, ApiClient } from './client';
import type { ApiError, ApiRequestOptions, UseApiOptions } from './types';

/**
 * Generic hook for GET requests with automatic fallback
 */
export function useApiQuery<TData = any>(
  apiType: 'backend' | 'agent',
  endpoint: string,
  options?: UseApiOptions<TData> & {
    agentName?: string;
    agentId?: string;
    sessionId?: string;
  }
) {
  const {
    queryKey = [apiType, endpoint],
    enabled = true,
    staleTime = 5 * 60 * 1000,
    retry = 1,
    fallbackData,
    onSuccess,
    onError,
    agentName,
    agentId,
    sessionId,
  } = options || {};

  return useQuery<TData, ApiError>({
    queryKey,
    queryFn: async () => {
      try {
        const response =
          apiType === 'backend'
            ? await api.backend.get<TData>(endpoint)
            : await api.agent.get<TData>(endpoint, { agentName, agentId, sessionId });

        if (!response.ok && fallbackData) {
          console.warn(
            `API call to ${endpoint} failed (${response.status}), using fallback data`
          );
          return fallbackData;
        }

        return response.data;
      } catch (error: any) {
        if (fallbackData) {
          console.warn(
            `API call to ${endpoint} failed with error, using fallback data:`,
            error
          );
          return fallbackData;
        }
        throw error;
      }
    },
    enabled,
    staleTime,
    retry,
    // Use placeholderData instead of initialData so queries still run
    placeholderData: fallbackData,
  } as UseQueryOptions<TData, ApiError>);
}

/**
 * Generic hook for POST/PUT/PATCH/DELETE mutations
 */
export function useApiMutation<TData = any, TVariables = any>(
  apiType: 'backend' | 'agent',
  endpoint: string,
  options?: {
    method?: 'POST' | 'PUT' | 'PATCH' | 'DELETE';
    agentName?: string;
    retry?: boolean;
    onMutate?: (variables: TVariables) => Promise<any> | any;
    onSuccess?: (data: TData, variables: TVariables, context?: any) => void;
    onError?: (error: ApiError, variables: TVariables, context?: any) => void;
    onSettled?: (data: TData | undefined, error: ApiError | null, variables: TVariables, context?: any) => void;
  }
) {
  const {
    method = 'POST',
    agentName,
    retry,
    onMutate,
    onSuccess,
    onError,
    onSettled,
  } = options || {};

  return useMutation<TData, ApiError, TVariables>({
    mutationFn: async (variables: TVariables) => {
      // Handle path parameters (e.g., /tasks/:id)
      let finalEndpoint = endpoint;
      if (typeof variables === 'object' && variables !== null && 'id' in variables) {
        finalEndpoint = endpoint.replace(':id', (variables as any).id);
      }

      const requestOptions: ApiRequestOptions = {
        method,
        body: variables,
      };

      const response =
        apiType === 'backend'
          ? await ApiClient.backend<TData>(finalEndpoint, requestOptions)
          : await ApiClient.agent<TData>(finalEndpoint, {
              ...requestOptions,
              agentName,
            });

      if (!response.ok) {
        throw {
          message: `Request failed with status ${response.status}`,
          status: response.status,
          error: response.data,
        } as ApiError;
      }

      return response.data;
    },
    retry,
    onMutate,
    onSuccess,
    onError,
    onSettled,
  } as UseMutationOptions<TData, ApiError, TVariables>);
}

/**
 * Backend-specific hooks
 */
export const useBackendQuery = <TData = any>(
  endpoint: string,
  options?: UseApiOptions<TData>
) => useApiQuery<TData>('backend', endpoint, options);

export const useBackendMutation = <TData = any, TVariables = any>(
  endpoint: string,
  options?: Parameters<typeof useApiMutation<TData, TVariables>>[2]
) => useApiMutation<TData, TVariables>('backend', endpoint, options);

/**
 * Agent-specific hooks
 */
export const useAgentQuery = <TData = any>(
  endpoint: string,
  options?: UseApiOptions<TData> & {
    agentName?: string;
    agentId?: string;
    sessionId?: string;
  }
) => {
  // Agent queries have shorter timeout and no retries (fail fast)
  return useApiQuery<TData>('agent', endpoint, {
    retry: false, // Don't retry agent queries - they either work or don't
    staleTime: 0, // Always fetch fresh from agent
    ...options,
  });
};

export const useAgentMutation = <TData = any, TVariables = any>(
  endpoint: string,
  options?: Parameters<typeof useApiMutation<TData, TVariables>>[2]
) => {
  // Agent mutations also don't retry - graceful degradation
  return useApiMutation<TData, TVariables>('agent', endpoint, {
    retry: false,
    ...options,
  });
};

/**
 * Cross-session agent communication hook
 */
export function useCrossSessionAgent<TData = any>(
  endpoint: string,
  sessionId: string,
  options?: UseApiOptions<TData> & {
    agentName?: string;
    agentId?: string;
  }
) {
  return useAgentQuery<TData>(endpoint, {
    ...options,
    sessionId,
    queryKey: ['agent', 'session', sessionId, endpoint],
  });
}

/**
 * Multi-agent query hook (queries multiple agents in parallel)
 */
export function useMultiAgentQuery<TData = any>(
  endpoint: string,
  agentNames: string[],
  options?: UseApiOptions<TData[]>
) {
  const queries = agentNames.map((agentName) =>
    useAgentQuery<TData>(endpoint, {
      ...options,
      agentName,
      queryKey: ['agent', agentName, endpoint],
    })
  );

  return {
    data: queries.map((q) => q.data).filter(Boolean) as TData[],
    isLoading: queries.some((q) => q.isLoading),
    isError: queries.some((q) => q.isError),
    errors: queries.map((q) => q.error).filter(Boolean),
    queries,
  };
}
