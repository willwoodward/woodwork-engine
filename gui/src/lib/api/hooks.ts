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
    initialData: fallbackData,
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
    onSuccess?: (data: TData, variables: TVariables) => void;
    onError?: (error: ApiError, variables: TVariables) => void;
  }
) {
  const { method = 'POST', agentName, onSuccess, onError } = options || {};

  return useMutation<TData, ApiError, TVariables>({
    mutationFn: async (variables: TVariables) => {
      const requestOptions: ApiRequestOptions = {
        method,
        body: variables,
      };

      const response =
        apiType === 'backend'
          ? await ApiClient.backend<TData>(endpoint, requestOptions)
          : await ApiClient.agent<TData>(endpoint, {
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
    onSuccess,
    onError,
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
) => useApiQuery<TData>('agent', endpoint, options);

export const useAgentMutation = <TData = any, TVariables = any>(
  endpoint: string,
  options?: Parameters<typeof useApiMutation<TData, TVariables>>[2]
) => useApiMutation<TData, TVariables>('agent', endpoint, options);

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
