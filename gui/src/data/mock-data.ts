// Centralized mock data for all features

export interface MockWorkflowStep {
  name: string;
  tool: string;
  description: string;
}

export interface MockWorkflow {
  id: string;
  name: string;
  steps: MockWorkflowStep[];
}

export interface MockChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface MockChatSession {
  id: string;
  name: string;
  messages: MockChatMessage[];
  createdAt: Date;
  updatedAt: Date;
}

// Mock Workflows
export const mockWorkflows: MockWorkflow[] = [
  {
    id: "workflow-1",
    name: "Data Processing Pipeline",
    steps: [
      { name: "Load Data", tool: "file_reader", description: "Read CSV files from input directory" },
      { name: "Clean Data", tool: "data_cleaner", description: "Remove duplicates and handle missing values" },
      { name: "Transform", tool: "transformer", description: "Apply business logic transformations" },
      { name: "Validate", tool: "validator", description: "Check data quality and constraints" },
      { name: "Save Results", tool: "file_writer", description: "Write processed data to output" }
    ]
  },
  {
    id: "workflow-2",
    name: "AI Model Training",
    steps: [
      { name: "Prepare Dataset", tool: "dataset_loader", description: "Load and split training data" },
      { name: "Feature Engineering", tool: "feature_extractor", description: "Extract and select relevant features" },
      { name: "Train Model", tool: "ml_trainer", description: "Train machine learning model" },
      { name: "Evaluate", tool: "evaluator", description: "Test model performance" }
    ]
  },
  {
    id: "workflow-3",
    name: "API Integration",
    steps: [
      { name: "Authenticate", tool: "auth_handler", description: "Handle API authentication" },
      { name: "Fetch Data", tool: "api_client", description: "Retrieve data from external API" },
      { name: "Process Response", tool: "response_processor", description: "Parse and validate API response" }
    ]
  }
];

// Mock Chat Data
export const mockChatSessions: MockChatSession[] = [
  {
    id: "chat-1",
    name: "Getting Started",
    createdAt: new Date('2024-01-15T10:00:00Z'),
    updatedAt: new Date('2024-01-15T10:30:00Z'),
    messages: [
      {
        id: "msg-1",
        role: "user",
        content: "Hello! I'd like to learn about creating workflows.",
        timestamp: new Date('2024-01-15T10:00:00Z')
      },
      {
        id: "msg-2",
        role: "assistant",
        content: "Welcome! I'd be happy to help you create workflows. You can use the Workflow Builder to drag and drop tools to create custom data processing pipelines. Would you like me to guide you through creating your first workflow?",
        timestamp: new Date('2024-01-15T10:01:00Z')
      },
      {
        id: "msg-3",
        role: "user",
        content: "Yes, that would be great! How do I get started?",
        timestamp: new Date('2024-01-15T10:05:00Z')
      },
      {
        id: "msg-4",
        role: "assistant",
        content: "Great! Here's how to get started:\n\n1. Navigate to the Workflows page\n2. Click the '+' button to create a new workflow\n3. Drag tools from the palette on the left\n4. Configure each step in the right panel\n5. Save and run your workflow\n\nWould you like me to explain any specific tool types?",
        timestamp: new Date('2024-01-15T10:06:00Z')
      }
    ]
  },
  {
    id: "chat-2",
    name: "Data Processing Help",
    createdAt: new Date('2024-01-16T14:00:00Z'),
    updatedAt: new Date('2024-01-16T14:15:00Z'),
    messages: [
      {
        id: "msg-5",
        role: "user",
        content: "I need help processing CSV files. What tools should I use?",
        timestamp: new Date('2024-01-16T14:00:00Z')
      },
      {
        id: "msg-6",
        role: "assistant",
        content: "For CSV processing, I recommend this workflow:\n\n1. **File Reader** - Load your CSV files\n2. **Data Cleaner** - Remove duplicates and handle missing values\n3. **Transformer** - Apply any data transformations\n4. **Validator** - Check data quality\n5. **File Writer** - Save the processed results\n\nWould you like me to help you configure any of these steps?",
        timestamp: new Date('2024-01-16T14:01:00Z')
      }
    ]
  }
];

// Default chat response for new conversations
export const defaultChatResponse = "Hello! I'm here to help you with creating workflows, understanding your data processing needs, and guiding you through the platform. How can I assist you today?";

// Human Input Request Types
export interface MockHumanInputRequest {
  id: string;
  type: 'approval' | 'edit_content' | 'confirmation' | 'choice' | 'ask_user';
  title: string;
  description: string;
  agentName: string;
  workflowName?: string;
  status: 'pending' | 'approved' | 'rejected' | 'completed';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  timestamp: Date;
  content?: string; // For editable content
  originalContent?: string; // For comparing changes
  metadata?: {
    command?: string;
    options?: string[];
    context?: string;
    question?: string;
    timeout_seconds?: number;
  };
  // Cross-session context for API integration
  sessionId?: string;
  apiInputId?: string;
}

// Mock Human Input Requests
export const mockHumanInputRequests: MockHumanInputRequest[] = [
  {
    id: "req-1",
    type: "approval",
    title: "Permission to Delete Old Log Files",
    description: "AI Agent needs permission to delete log files older than 30 days to free up disk space (2.3GB).",
    agentName: "System Maintenance Agent",
    workflowName: "Daily Cleanup",
    status: "pending",
    priority: "medium",
    timestamp: new Date('2024-01-15T14:30:00Z'),
    metadata: {
      command: "rm -rf /var/logs/*.log",
      context: "Disk usage at 87% - need to clean up space"
    }
  },
  {
    id: "req-2",
    type: "edit_content",
    title: "Review Email to Client About Project Delay",
    description: "Please review and edit this email before sending to the client about the project timeline adjustment.",
    agentName: "Communication Agent",
    workflowName: "Client Management",
    status: "pending",
    priority: "high",
    timestamp: new Date('2024-01-15T13:45:00Z'),
    content: "Dear Mr. Johnson,\n\nI hope this email finds you well. I wanted to reach out regarding the timeline for the data processing project we discussed.\n\nUnfortunately, we've encountered some technical challenges that will require an additional 2 weeks to resolve properly. This will ensure the highest quality deliverable for your team.\n\nI apologize for any inconvenience this may cause and appreciate your understanding.\n\nBest regards,\nThe Development Team",
    originalContent: "Dear Mr. Johnson,\n\nI hope this email finds you well. I wanted to reach out regarding the timeline for the data processing project we discussed.\n\nUnfortunately, we've encountered some technical challenges that will require an additional 2 weeks to resolve properly. This will ensure the highest quality deliverable for your team.\n\nI apologize for any inconvenience this may cause and appreciate your understanding.\n\nBest regards,\nThe Development Team"
  },
  {
    id: "req-3",
    type: "confirmation",
    title: "Deploy Model to Production Environment",
    description: "ML model training completed successfully. Ready to deploy to production with 94.2% accuracy. Confirm deployment?",
    agentName: "ML Training Agent",
    workflowName: "Model Pipeline",
    status: "pending",
    priority: "high",
    timestamp: new Date('2024-01-15T12:20:00Z'),
    metadata: {
      context: "Model accuracy: 94.2% (target: 90%+), Test data performance: 92.8%"
    }
  },
  {
    id: "req-4",
    type: "choice",
    title: "Choose Data Processing Strategy",
    description: "Multiple viable approaches detected for processing the new dataset. Please select preferred method.",
    agentName: "Data Processing Agent",
    workflowName: "Data Ingestion",
    status: "pending",
    priority: "medium",
    timestamp: new Date('2024-01-15T11:15:00Z'),
    metadata: {
      options: [
        "Batch processing (slower but more reliable)",
        "Stream processing (faster but requires more monitoring)",
        "Hybrid approach (balanced performance and reliability)"
      ]
    }
  },
  {
    id: "req-5",
    type: "approval",
    title: "Install Additional Python Dependencies",
    description: "Workflow requires new packages: pandas v2.1.0, scikit-learn v1.3.0. Install these dependencies?",
    agentName: "Package Manager Agent",
    workflowName: "Environment Setup",
    status: "approved",
    priority: "low",
    timestamp: new Date('2024-01-14T16:30:00Z'),
    metadata: {
      command: "pip install pandas==2.1.0 scikit-learn==1.3.0"
    }
  },
  {
    id: "req-6",
    type: "edit_content",
    title: "Customize API Documentation Template",
    description: "Generated API documentation needs human review and customization before publishing.",
    agentName: "Documentation Agent",
    workflowName: "API Documentation",
    status: "completed",
    priority: "low",
    timestamp: new Date('2024-01-14T10:00:00Z'),
    content: "# Data Processing API\n\n## Overview\nThis API provides endpoints for processing and analyzing data workflows.\n\n## Authentication\nAll requests require an API key in the header:\n```\nAuthorization: Bearer YOUR_API_KEY\n```\n\n## Endpoints\n\n### POST /api/workflows\nCreate a new workflow...",
    originalContent: "# Data Processing API\n\n## Overview\nThis API provides endpoints for processing and analyzing data workflows.\n\n## Authentication\nAll requests require an API key in the header:\n```\nAuthorization: Bearer YOUR_API_KEY\n```\n\n## Endpoints\n\n### POST /api/workflows\nCreate a new workflow..."
  }
];

