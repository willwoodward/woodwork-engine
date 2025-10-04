/**
 * API Abstraction Layer
 *
 * Provides a unified interface for communicating with:
 * - Backend API (web app server)
 * - AI Agent APIs (can be cross-session, multi-host)
 *
 * @example
 * ```typescript
 * import { useBackendQuery, useAgentMutation, api, setAgentEndpoint } from '@/lib/api';
 *
 * // Query backend
 * const { data: tasks } = useBackendQuery('/tasks', { fallbackData: mockTasks });
 *
 * // Mutate agent
 * const workflow = useAgentMutation('/execute-workflow', {
 *   agentName: 'workflow-agent',
 *   onSuccess: (data) => console.log('Workflow completed', data)
 * });
 *
 * // Add new agent endpoint dynamically
 * setAgentEndpoint('remote-agent', {
 *   baseUrl: 'http://192.168.1.100:5000',
 *   agentId: 'agent-123'
 * });
 * ```
 */

// Core client
export { api, ApiClient } from './client';

// Configuration
export {
  getApiConfig,
  updateApiConfig,
  setAgentEndpoint,
  getAgentEndpoint,
  defaultApiConfig,
} from './config';

// React hooks
export {
  useApiQuery,
  useApiMutation,
  useBackendQuery,
  useBackendMutation,
  useAgentQuery,
  useAgentMutation,
  useCrossSessionAgent,
  useMultiAgentQuery,
} from './hooks';

// Types
export type {
  ApiType,
  ApiEndpoint,
  AgentEndpoint,
  ApiConfig,
  ApiRequestOptions,
  ApiResponse,
  ApiError,
  UseApiOptions,
} from './types';
