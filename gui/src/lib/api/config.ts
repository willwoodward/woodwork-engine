import type { ApiConfig } from './types';

/**
 * Default API configuration
 * Can be overridden via environment variables or runtime configuration
 */
export const defaultApiConfig: ApiConfig = {
  backend: {
    baseUrl: process.env.VITE_BACKEND_URL || 'http://localhost:8001', // Personal server
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
  },
  agents: {
    default: {
      baseUrl: process.env.VITE_AGENT_URL || 'http://localhost:8000', // Main Woodwork agent
      wsUrl: process.env.VITE_AGENT_WS_URL || 'ws://localhost:8000',
      timeout: 60000, // Agents may need more time
      headers: {
        'Content-Type': 'application/json',
      },
    },
  },
};

/**
 * In-memory configuration that can be updated at runtime
 */
let currentConfig: ApiConfig = { ...defaultApiConfig };

/**
 * Get the current API configuration
 */
export function getApiConfig(): ApiConfig {
  return currentConfig;
}

/**
 * Update the API configuration
 * Useful for adding new agent endpoints dynamically
 */
export function updateApiConfig(updates: Partial<ApiConfig>) {
  currentConfig = {
    ...currentConfig,
    ...updates,
    agents: {
      ...currentConfig.agents,
      ...(updates.agents || {}),
    },
  };
}

/**
 * Add or update a specific agent endpoint
 */
export function setAgentEndpoint(name: string, endpoint: ApiConfig['agents']['default']) {
  currentConfig.agents[name] = endpoint;
}

/**
 * Get agent endpoint by name or use default
 */
export function getAgentEndpoint(name?: string) {
  return name && currentConfig.agents[name]
    ? currentConfig.agents[name]
    : currentConfig.agents.default;
}
