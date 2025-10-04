/**
 * Core API types and interfaces for the application
 * Supports both AI Agent APIs and Web Backend APIs
 */

export type ApiType = 'agent' | 'backend';

export interface ApiEndpoint {
  /** Base URL for the API */
  baseUrl: string;
  /** Optional timeout in milliseconds */
  timeout?: number;
  /** Optional headers to include with every request */
  headers?: Record<string, string>;
}

export interface AgentEndpoint extends ApiEndpoint {
  /** Agent ID for cross-session communication */
  agentId?: string;
  /** Session ID for agent communication */
  sessionId?: string;
  /** WebSocket URL for real-time communication */
  wsUrl?: string;
}

export interface ApiConfig {
  /** Backend API configuration */
  backend: ApiEndpoint;
  /** Agent API configurations (can have multiple agents on different hosts) */
  agents: {
    /** Default agent endpoint */
    default: AgentEndpoint;
    /** Named agent endpoints for specific agents */
    [agentName: string]: AgentEndpoint;
  };
}

export interface ApiRequestOptions {
  /** HTTP method */
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  /** Request body */
  body?: any;
  /** Additional headers */
  headers?: Record<string, string>;
  /** Query parameters */
  params?: Record<string, string | number | boolean>;
  /** Timeout override */
  timeout?: number;
  /** Agent ID for agent-specific requests */
  agentId?: string;
  /** Session ID for session-specific requests */
  sessionId?: string;
}

export interface ApiResponse<T = any> {
  /** Response data */
  data: T;
  /** HTTP status code */
  status: number;
  /** Response headers */
  headers: Headers;
  /** Whether the request was successful */
  ok: boolean;
}

export interface ApiError {
  /** Error message */
  message: string;
  /** HTTP status code */
  status?: number;
  /** Original error */
  error?: any;
  /** Request that caused the error */
  request?: {
    url: string;
    method: string;
    body?: any;
  };
}

export interface UseApiOptions<TData = any, TError = ApiError> {
  /** Query key for caching */
  queryKey?: string[];
  /** Enable/disable the query */
  enabled?: boolean;
  /** Stale time in milliseconds */
  staleTime?: number;
  /** Retry count */
  retry?: number;
  /** Fallback data when API fails */
  fallbackData?: TData;
  /** Success callback */
  onSuccess?: (data: TData) => void;
  /** Error callback */
  onError?: (error: TError) => void;
}
