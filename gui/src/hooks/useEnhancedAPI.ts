// Enhanced API hooks for the FastAPI GUI server backend
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRef, useEffect, useState, useCallback } from 'react';
import type {
  WorkflowTriggerRequest,
  WorkflowExecutionResult,
  HumanInputRequest,
  HumanInputResponse,
  WebSocketMessage,
  AgentsResponse,
  WorkflowsResponse,
  InboxResponse
} from '@/types/api-types';

// Enhanced API base URL - can be configured
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || '';

// WebSocket hook for real-time communication
export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const websocketRef = useRef<WebSocket | null>(null);
  const messageHandlersRef = useRef<Map<string, (data: any) => void>>(new Map());

  const connect = useCallback(() => {
    try {
      // Use native WebSocket for FastAPI
      const wsUrl = `ws://${window.location.host}/ws`;
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
        console.log('WebSocket connected');
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);

          // Call registered handlers for this message type
          const handler = messageHandlersRef.current.get(message.type);
          if (handler) {
            handler(message.payload);
          }

          // Dispatch custom event for other components
          window.dispatchEvent(new CustomEvent('websocket-message', {
            detail: message
          }));

        } catch (e) {
          console.error('Error parsing WebSocket message:', e);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        console.log('WebSocket disconnected');

        // Attempt reconnection after 3 seconds
        setTimeout(connect, 3000);
      };

      ws.onerror = (err) => {
        setError(new Error('WebSocket connection failed'));
        console.error('WebSocket error:', err);
      };

      websocketRef.current = ws;

    } catch (err) {
      setError(err as Error);
    }
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, []);

  const addMessageHandler = useCallback((messageType: string, handler: (data: any) => void) => {
    messageHandlersRef.current.set(messageType, handler);
  }, []);

  const removeMessageHandler = useCallback((messageType: string) => {
    messageHandlersRef.current.delete(messageType);
  }, []);

  useEffect(() => {
    connect();

    return () => {
      websocketRef.current?.close();
    };
  }, [connect]);

  return {
    isConnected,
    error,
    sendMessage,
    addMessageHandler,
    removeMessageHandler
  };
}

// Hook for fetching workflows
export function useWorkflows(filters?: {
  category?: string;
  search?: string;
  status?: string;
  limit?: number;
}) {
  return useQuery<WorkflowsResponse>({
    queryKey: ['workflows', filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters?.category) params.append('category', filters.category);
      if (filters?.search) params.append('search', filters.search);
      if (filters?.status) params.append('status', filters.status);
      if (filters?.limit) params.append('limit', filters.limit.toString());

      const response = await fetch(`${API_BASE_URL}/api/workflows?${params}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch workflows: ${response.statusText}`);
      }
      return response.json();
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Hook for fetching agents
export function useAgents() {
  return useQuery<AgentsResponse>({
    queryKey: ['agents'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/api/agents`);
      if (!response.ok) {
        throw new Error(`Failed to fetch agents: ${response.statusText}`);
      }
      return response.json();
    },
    refetchInterval: 30 * 1000, // Refresh every 30 seconds for live status
  });
}

// Hook for triggering workflows
export function useTriggerWorkflow() {
  const queryClient = useQueryClient();

  return useMutation<WorkflowExecutionResult, Error, WorkflowTriggerRequest>({
    mutationFn: async (request) => {
      const response = await fetch(`${API_BASE_URL}/api/workflows/trigger`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to trigger workflow: ${response.statusText}`);
      }

      return response.json();
    },
    onSuccess: (data) => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['executions'] });

      console.log(`Workflow triggered successfully. Execution ID: ${data.executionId}`);
    },
    onError: (error) => {
      console.error(`Failed to trigger workflow: ${error.message}`);
    }
  });
}

// Hook for inbox requests
export function useInboxRequests() {
  const [requests, setRequests] = useState<HumanInputRequest[]>([]);
  const { addMessageHandler, removeMessageHandler } = useWebSocket();

  // Initial fetch
  const { data, isLoading, error } = useQuery<InboxResponse>({
    queryKey: ['inbox-requests'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/api/inbox/requests`);
      if (!response.ok) {
        throw new Error(`Failed to fetch inbox requests: ${response.statusText}`);
      }
      return response.json();
    },
  });

  // Update local state when data changes
  useEffect(() => {
    if (data?.requests) {
      setRequests(data.requests);
    }
  }, [data]);

  // Listen for real-time inbox updates
  useEffect(() => {
    const handleInboxUpdate = (payload: any) => {
      if (payload.new_request) {
        setRequests(prev => [...prev, payload.new_request]);
      }
      if (payload.completed_request) {
        setRequests(prev =>
          prev.filter(req => req.request_id !== payload.completed_request)
        );
      }
    };

    addMessageHandler('inbox_update', handleInboxUpdate);

    return () => {
      removeMessageHandler('inbox_update');
    };
  }, [addMessageHandler, removeMessageHandler]);

  return {
    requests,
    isLoading,
    error
  };
}

// Hook for responding to inbox requests
export function useInboxResponse() {
  const queryClient = useQueryClient();
  const { sendMessage } = useWebSocket();

  return useMutation<void, Error, HumanInputResponse>({
    mutationFn: async (response) => {
      // Try WebSocket first, fall back to REST
      const success = sendMessage({
        type: 'human_input_response',
        payload: response
      });

      if (!success) {
        // Fallback to REST API
        const httpResponse = await fetch(`${API_BASE_URL}/api/inbox/respond`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(response)
        });

        if (!httpResponse.ok) {
          throw new Error(`Failed to respond to request: ${httpResponse.statusText}`);
        }
      }
    },
    onSuccess: () => {
      // Invalidate inbox requests to refresh the list
      queryClient.invalidateQueries({ queryKey: ['inbox-requests'] });
    },
    onError: (error) => {
      console.error(`Failed to respond to inbox request: ${error.message}`);
    }
  });
}

// Hook for multi-agent chat sessions
export function useMultiAgentChat() {
  const [activeSessions, setActiveSessions] = useState<Map<string, any>>(new Map());
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const { sendMessage, addMessageHandler, removeMessageHandler } = useWebSocket();

  const connectToAgent = useCallback(async (agentId: string) => {
    const sessionId = `session_${Date.now()}_${agentId}`;

    // Request connection to agent
    const success = sendMessage({
      type: 'connect_to_agent',
      payload: {
        sessionId,
        agentId,
        userId: 'current_user' // TODO: Get from auth context
      }
    });

    if (success) {
      const newSession = {
        sessionId,
        agentId,
        agentName: agentId, // TODO: Get from agents list
        messages: [],
        status: 'connecting'
      };

      setActiveSessions(prev => new Map(prev).set(sessionId, newSession));
      setSelectedSession(sessionId);

      return sessionId;
    }

    throw new Error('Failed to connect to agent');
  }, [sendMessage]);

  const sendToAgent = useCallback((sessionId: string, message: string) => {
    sendMessage({
      type: 'agent_message',
      payload: {
        sessionId,
        message: {
          type: 'user_input',
          input: message
        }
      }
    });

    // Optimistically add user message
    setActiveSessions(prev => {
      const updated = new Map(prev);
      const session = updated.get(sessionId);
      if (session) {
        session.messages.push({
          id: `msg_${Date.now()}`,
          type: 'user',
          content: message,
          timestamp: new Date()
        });
        updated.set(sessionId, session);
      }
      return updated;
    });
  }, [sendMessage]);

  // Listen for agent messages
  useEffect(() => {
    const handleAgentMessage = (payload: any) => {
      const { sessionId, message } = payload;

      setActiveSessions(prev => {
        const updated = new Map(prev);
        const session = updated.get(sessionId);
        if (session) {
          session.messages.push({
            id: `msg_${Date.now()}`,
            type: 'agent',
            content: message.content || message.response || 'No content',
            timestamp: new Date(),
            metadata: message.metadata
          });
          session.status = 'connected';
          updated.set(sessionId, session);
        }
        return updated;
      });
    };

    addMessageHandler('agent_message', handleAgentMessage);

    return () => {
      removeMessageHandler('agent_message');
    };
  }, [addMessageHandler, removeMessageHandler]);

  return {
    activeSessions: Array.from(activeSessions.values()),
    selectedSession,
    setSelectedSession,
    connectToAgent,
    sendToAgent
  };
}