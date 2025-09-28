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

// Export types for external use
export type { MockWorkflowStep, MockWorkflow, MockChatMessage, MockChatSession };