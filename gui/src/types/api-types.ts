// API types that match the enhanced GUI server backend

export interface Agent {
  id: string;
  name: string;
  capabilities: string[];
  status: 'online' | 'offline' | 'busy';
  api_input_id: string;
  source: string;
  currentSessions?: number;
  lastActivity?: string;
  tools?: string[];
}

export interface Workflow {
  id: string;
  name: string;
  description?: string;
  category?: string;
  status?: 'active' | 'cached' | 'archived';
  requiredCapabilities?: string[];
  steps?: WorkflowStep[];
  metadata?: Record<string, any>;
}

export interface WorkflowStep {
  name: string;
  tool: string;
  description: string;
  inputs?: Record<string, any>;
  outputs?: Record<string, any>;
}

export interface WorkflowTriggerRequest {
  workflowId: string;
  inputs: Record<string, any>;
  targetAgent?: string;
  priority?: 'low' | 'medium' | 'high';
  sessionId?: string;
}

export interface WorkflowExecutionResult {
  executionId: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  estimatedDuration?: number;
  targetAgent?: string;
}

export interface HumanInputRequest {
  request_id: string;
  type: 'approval' | 'edit_content' | 'confirmation' | 'choice' | 'ask_user';
  title: string;
  description: string;
  context?: string;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  agent_name: string;
  session_id: string;
  api_input_id: string;
  workflow_name?: string;
  created_at: string;
  metadata?: {
    command?: string;
    options?: string[];
    content?: string;
    question?: string;
    timeout_seconds?: number;
  };
}

export interface HumanInputResponse {
  request_id: string;
  action: 'approved' | 'rejected' | 'edited' | 'selected' | 'responded';
  data?: string;
  user_id: string;
  responded_at: string;
}

export interface ChatSession {
  sessionId: string;
  agentId: string;
  agentName: string;
  messages: ChatMessage[];
  status: 'connecting' | 'connected' | 'disconnected';
  createdAt: Date;
  lastActive: Date;
}

export interface ChatMessage {
  id: string;
  type: 'user' | 'agent' | 'system';
  content: string;
  timestamp: Date;
  metadata?: {
    agentThought?: string;
    toolCall?: string;
    error?: string;
  };
}

export interface AgentEvent {
  event: 'agent.thought' | 'agent.action' | 'agent.response' | 'tool.call' | 'tool.observation' | 'agent.error' | 'human.input.required';
  payload: any;
  sender: string;
  session_id: string;
  timestamp: number;
}

export interface APIInputConfig {
  id: string;
  host: string;
  port: number;
  agents: string[];
  priority?: number;
  auth?: {
    type: string;
    token?: string;
  };
}

// API Response types
export interface WorkflowsResponse {
  workflows: Workflow[];
  total?: number;
  categories?: string[];
}

export interface AgentsResponse {
  agents: Agent[];
  capabilities?: string[];
  apiInputs?: APIInputConfig[];
}

export interface InboxResponse {
  requests: HumanInputRequest[];
  total?: number;
}

export interface WebSocketMessage {
  type: 'connection_established' | 'inbox_update' | 'agent_message' | 'human_input_response';
  payload: any;
}