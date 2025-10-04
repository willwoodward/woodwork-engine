import { getApiConfig, getAgentEndpoint } from './config';
import type { ApiRequestOptions, ApiResponse, ApiError, ApiType } from './types';

/**
 * Base API client that handles both backend and agent requests
 */
export class ApiClient {
  /**
   * Make a request to the backend API
   */
  static async backend<T = any>(
    endpoint: string,
    options?: ApiRequestOptions
  ): Promise<ApiResponse<T>> {
    const config = getApiConfig();
    return this.request<T>('backend', endpoint, {
      ...options,
      baseUrl: config.backend.baseUrl,
      defaultHeaders: config.backend.headers,
      timeout: options?.timeout || config.backend.timeout,
    });
  }

  /**
   * Make a request to an agent API
   */
  static async agent<T = any>(
    endpoint: string,
    options?: ApiRequestOptions & { agentName?: string }
  ): Promise<ApiResponse<T>> {
    const agentEndpoint = getAgentEndpoint(options?.agentName);

    return this.request<T>('agent', endpoint, {
      ...options,
      baseUrl: agentEndpoint.baseUrl,
      defaultHeaders: agentEndpoint.headers,
      timeout: options?.timeout || agentEndpoint.timeout,
      agentId: options?.agentId || agentEndpoint.agentId,
      sessionId: options?.sessionId || agentEndpoint.sessionId,
    });
  }

  /**
   * Core request method
   */
  private static async request<T>(
    type: ApiType,
    endpoint: string,
    options: ApiRequestOptions & {
      baseUrl?: string;
      defaultHeaders?: Record<string, string>;
    }
  ): Promise<ApiResponse<T>> {
    const {
      method = 'GET',
      body,
      headers = {},
      params,
      timeout = 30000,
      baseUrl = '',
      defaultHeaders = {},
      agentId,
      sessionId,
    } = options;

    // Build URL with query params
    const url = new URL(endpoint, baseUrl);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        url.searchParams.append(key, String(value));
      });
    }

    // Build headers
    const requestHeaders: Record<string, string> = {
      ...defaultHeaders,
      ...headers,
    };

    // Add agent/session IDs to headers if present
    if (agentId) {
      requestHeaders['X-Agent-Id'] = agentId;
    }
    if (sessionId) {
      requestHeaders['X-Session-Id'] = sessionId;
    }

    // Create abort controller for timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(url.toString(), {
        method,
        headers: requestHeaders,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // Parse response
      let data: T;
      const contentType = response.headers.get('content-type');

      if (contentType?.includes('application/json')) {
        data = await response.json();
      } else {
        data = (await response.text()) as any;
      }

      return {
        data,
        status: response.status,
        headers: response.headers,
        ok: response.ok,
      };
    } catch (error: any) {
      clearTimeout(timeoutId);

      const apiError: ApiError = {
        message: error.message || 'Request failed',
        error,
        request: {
          url: url.toString(),
          method,
          body,
        },
      };

      throw apiError;
    }
  }
}

/**
 * Convenience methods for common HTTP verbs
 */
export const api = {
  backend: {
    get: <T>(endpoint: string, options?: Omit<ApiRequestOptions, 'method'>) =>
      ApiClient.backend<T>(endpoint, { ...options, method: 'GET' }),

    post: <T>(endpoint: string, body?: any, options?: Omit<ApiRequestOptions, 'method' | 'body'>) =>
      ApiClient.backend<T>(endpoint, { ...options, method: 'POST', body }),

    put: <T>(endpoint: string, body?: any, options?: Omit<ApiRequestOptions, 'method' | 'body'>) =>
      ApiClient.backend<T>(endpoint, { ...options, method: 'PUT', body }),

    delete: <T>(endpoint: string, options?: Omit<ApiRequestOptions, 'method'>) =>
      ApiClient.backend<T>(endpoint, { ...options, method: 'DELETE' }),

    patch: <T>(endpoint: string, body?: any, options?: Omit<ApiRequestOptions, 'method' | 'body'>) =>
      ApiClient.backend<T>(endpoint, { ...options, method: 'PATCH', body }),
  },

  agent: {
    get: <T>(endpoint: string, options?: Omit<ApiRequestOptions, 'method'> & { agentName?: string }) =>
      ApiClient.agent<T>(endpoint, { ...options, method: 'GET' }),

    post: <T>(endpoint: string, body?: any, options?: Omit<ApiRequestOptions, 'method' | 'body'> & { agentName?: string }) =>
      ApiClient.agent<T>(endpoint, { ...options, method: 'POST', body }),

    put: <T>(endpoint: string, body?: any, options?: Omit<ApiRequestOptions, 'method' | 'body'> & { agentName?: string }) =>
      ApiClient.agent<T>(endpoint, { ...options, method: 'PUT', body }),

    delete: <T>(endpoint: string, options?: Omit<ApiRequestOptions, 'method'> & { agentName?: string }) =>
      ApiClient.agent<T>(endpoint, { ...options, method: 'DELETE' }),

    patch: <T>(endpoint: string, body?: any, options?: Omit<ApiRequestOptions, 'method' | 'body'> & { agentName?: string }) =>
      ApiClient.agent<T>(endpoint, { ...options, method: 'PATCH', body }),
  },
};
