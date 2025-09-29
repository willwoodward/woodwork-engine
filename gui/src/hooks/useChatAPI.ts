// Enhanced chat API hook that connects to FastAPI backend
import { useMutation, useQuery } from '@tanstack/react-query';
import { useState, useEffect, useRef, useCallback } from 'react';

// Enhanced API base URL
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || '';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  type?: 'message' | 'event' | 'thought' | 'action' | 'error';
  metadata?: {
    event_type?: string;
    component_id?: string;
    component_type?: string;
    session_id?: string;
  };
  thinking?: string[]; // Array of thinking/event indicators
  isThinking?: boolean; // Current thinking state
}

// interface ChatInputRequest {
//   message: string;
//   session_id?: string;
// }

interface ChatInputResponse {
  status: string;
  session_id: string;
  message: string;
}

interface WebSocketEvent {
  type: string;
  payload: any;
  timestamp?: string;
}

export function useChatAPI() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string>('');
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [pendingUserRequest, setPendingUserRequest] = useState<{request_id: string, question: string} | null>(null);

  // Send message mutation
  const sendMessage = useMutation<ChatInputResponse, Error, {message: string, request_id?: string}>({
    mutationFn: async ({message, request_id}) => {
      const response = await fetch(`${API_BASE_URL}/api/input`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          input: message,
          request_id,
          session_id: sessionId || undefined
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to send message: ${response.statusText}`);
      }

      return response.json();
    },
    onSuccess: (data) => {
      // Update session ID if we got a new one
      if (data.session_id && data.session_id !== sessionId) {
        setSessionId(data.session_id);
      }
    },
  });

  // Get input status
  const { data: inputStatus } = useQuery({
    queryKey: ['input-status'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/api/input`);
      if (!response.ok) {
        throw new Error('Failed to get input status');
      }
      return response.json();
    },
    refetchInterval: 30000, // Check status every 30 seconds
  });

  // WebSocket connection for real-time events
  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const wsUrl = `ws://${window.location.host}/ws`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      // Send registration message if needed
      ws.send(JSON.stringify({
        type: 'register',
        payload: { client_type: 'chat_interface' }
      }));
    };

    ws.onmessage = (event) => {
      try {
        const data: WebSocketEvent = JSON.parse(event.data);
        handleWebSocketEvent(data);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
      // Attempt to reconnect after 3 seconds
      setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    };

    wsRef.current = ws;
  }, []);

  // Handle WebSocket events and convert them to chat messages
  const handleWebSocketEvent = useCallback((event: WebSocketEvent) => {
    const { type, payload, timestamp } = event;

    let messageContent = '';

    switch (type) {
      case 'agent.thought':
        messageContent = `💭 *thinking: ${payload.thought}*`;
        break;

      case 'agent.action':
        // messageContent = `🔧 *${payload.action}${payload.description ? ': ' + payload.description : ''}*`;
        break;

      case 'tool.call':
        const toolName = payload.tool || 'unknown';
        const params = payload.parameters;
        if (params && Object.keys(params).length > 0) {
          messageContent = `⚡ *calling ${toolName}*`;
        } else {
          messageContent = `⚡ *calling ${toolName}*`;
        }
        break;

      case 'tool.observation':
        const result = payload.observation || payload.result;
        if (typeof result === 'string' && result.length < 100) {
          messageContent = `📋 *result: ${result}*`;
        } else {
          messageContent = `📋 *tool completed*`;
        }
        break;

      case 'agent.step_complete':
        messageContent = `✅ *step completed*`;
        break;

      case 'agent.error':
        messageContent = `❌ *error: ${payload.error}*`;
        break;

      case 'agent.response':
        // This is an actual response, create a new assistant message and clear thinking state
        const assistantMessage: ChatMessage = {
          id: `response-${Date.now()}-${Math.random()}`,
          role: 'assistant',
          content: payload.response || payload.content || payload.message,
          timestamp: timestamp ? new Date(timestamp) : new Date(),
          type: 'message',
        };

        setMessages(prev => {
          // Find the last assistant thinking message and preserve its thinking history
          const lastMessage = prev[prev.length - 1];
          if (lastMessage && lastMessage.role === 'assistant' && (lastMessage.thinking || lastMessage.isThinking)) {
            const updatedLastMessage = {
              ...lastMessage,
              isThinking: false // Stop active thinking but preserve thinking array
            };
            return [...prev.slice(0, -1), updatedLastMessage, assistantMessage];
          }
          return [...prev, assistantMessage];
        });
        return;

      case 'user.input.request':
        // Agent is asking for user input - create a proper assistant message
        const question = payload.question || 'Please provide input:';
        const requestId = payload.request_id;
        setPendingUserRequest({ request_id: requestId, question });

        // Create a full assistant message for the question
        const assistantQuestionMessage: ChatMessage = {
          id: `ask-user-${requestId}`,
          role: 'assistant',
          content: question,
          timestamp: timestamp ? new Date(timestamp) : new Date(),
          type: 'message',
        };

        setMessages(prev => {
          // Find the last assistant thinking message and preserve its thinking history
          const lastMessage = prev[prev.length - 1];
          if (lastMessage && lastMessage.role === 'assistant' && (lastMessage.thinking || lastMessage.isThinking)) {
            const updatedLastMessage = {
              ...lastMessage,
              isThinking: false // Stop active thinking but preserve thinking array
            };
            return [...prev.slice(0, -1), updatedLastMessage, assistantQuestionMessage];
          }
          return [...prev, assistantQuestionMessage];
        });
        return;

      case 'connection_established':
        messageContent = `🔗 connected to ${payload.connected_api_inputs?.length || 0} agent(s)`;
        break;

      case 'input.received':
        // Skip these - they're just confirmations that input was received
        return;

      // Filter out internal events that shouldn't show in chat
      case 'register':
      case 'heartbeat':
      case 'status_update':
        return; // Don't create a chat message for these

      default:
        // Skip unknown events to keep chat clean
        return;
    }

    // For thinking/action events, create or update an assistant thinking message
    if (messageContent) {
      setMessages(prev => {
        const lastMessage = prev[prev.length - 1];

        // If last message is assistant and has thinking indicators, add to it
        if (lastMessage && lastMessage.role === 'assistant' && (lastMessage.thinking || lastMessage.isThinking)) {
          const updatedMessage = {
            ...lastMessage,
            thinking: [...(lastMessage.thinking || []), messageContent],
            isThinking: type.includes('thought') || type.includes('action')
          };

          return [...prev.slice(0, -1), updatedMessage];
        }

        // Otherwise, create a new assistant thinking message
        return [...prev, {
          id: `thinking-${Date.now()}-${Math.random()}`,
          role: 'assistant' as const,
          content: '', // No main content, just thinking indicators
          timestamp: timestamp ? new Date(timestamp) : new Date(),
          type: 'event' as const,
          thinking: [messageContent],
          isThinking: type.includes('thought') || type.includes('action')
        }];
      });
    }
  }, []);

  // Connect WebSocket on mount
  useEffect(() => {
    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connectWebSocket]);

  // Handle sending messages
  const handleSendMessage = useCallback(async (messageContent: string) => {
    // Check if this is a response to a pending user request
    const isResponse = pendingUserRequest !== null;
    const request_id = pendingUserRequest?.request_id;

    // Add user message immediately
    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: messageContent,
      timestamp: new Date(),
      type: 'message',
    };

    setMessages(prev => [...prev, userMessage]);

    // Send to backend
    try {
      await sendMessage.mutateAsync({message: messageContent, request_id});

      // Clear pending request if this was a response
      if (isResponse) {
        setPendingUserRequest(null);
      }
    } catch (error) {
      // Add error message
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `❌ **Failed to send message:** ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: new Date(),
        type: 'error',
      };
      setMessages(prev => [...prev, errorMessage]);
    }
  }, [sendMessage, pendingUserRequest]);

  return {
    messages,
    sendMessage: handleSendMessage,
    isLoading: sendMessage.isPending,
    isConnected,
    sessionId,
    inputStatus,
    pendingUserRequest,
    clearMessages: () => setMessages([]),
  };
}