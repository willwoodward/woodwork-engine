// Centralized mock data for all features

export interface MockWorkflowStep {
  name: string;
  tool: string;
  description: string;
  id?: string;
  inputs?: string;
  output?: string;
  sequence?: number;
  dependencies?: Array<{
    id: string;
    tool: string;
    action: string;
    output: string;
  }>;
}

export interface MockWorkflowMetadata {
  status?: string;
  created_at?: string;
  completed_at?: string;
  final_step?: number;
  action_count?: number;
  prompt?: string;
  total_actions?: number;
}

export interface MockWorkflowGraph {
  nodes: Array<{
    id: string;
    type: "prompt" | "action";
    label: string;
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    type: "starts" | "next" | "depends_on";
  }>;
}

export interface MockWorkflow {
  id: string;
  name: string;
  steps: MockWorkflowStep[];
  metadata?: MockWorkflowMetadata;
  graph?: MockWorkflowGraph;
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

// Mock Workflows with comprehensive metadata and graph structures
export const mockWorkflows: MockWorkflow[] = [
  {
    id: "workflow-1",
    name: "Data Processing Pipeline",
    steps: [
      {
        id: "step-1-1",
        name: "Load Data",
        tool: "file_reader",
        description: "Read CSV files from input directory",
        inputs: '{"file_path": "data/input.csv"}',
        output: "raw_data",
        sequence: 0
      },
      {
        id: "step-1-2",
        name: "Clean Data",
        tool: "data_cleaner",
        description: "Remove duplicates and handle missing values",
        inputs: '{"data": "raw_data"}',
        output: "cleaned_data",
        sequence: 1,
        dependencies: [{ id: "step-1-1", tool: "file_reader", action: "Load Data", output: "raw_data" }]
      },
      {
        id: "step-1-3",
        name: "Transform",
        tool: "transformer",
        description: "Apply business logic transformations",
        inputs: '{"data": "cleaned_data"}',
        output: "transformed_data",
        sequence: 2,
        dependencies: [{ id: "step-1-2", tool: "data_cleaner", action: "Clean Data", output: "cleaned_data" }]
      },
      {
        id: "step-1-4",
        name: "Validate",
        tool: "validator",
        description: "Check data quality and constraints",
        inputs: '{"data": "transformed_data"}',
        output: "validated_data",
        sequence: 3,
        dependencies: [{ id: "step-1-3", tool: "transformer", action: "Transform", output: "transformed_data" }]
      },
      {
        id: "step-1-5",
        name: "Save Results",
        tool: "file_writer",
        description: "Write processed data to output",
        inputs: '{"data": "validated_data", "output_path": "data/output.csv"}',
        output: "file_saved",
        sequence: 4,
        dependencies: [{ id: "step-1-4", tool: "validator", action: "Validate", output: "validated_data" }]
      }
    ],
    metadata: {
      status: "completed",
      created_at: "2024-01-15T10:00:00Z",
      completed_at: "2024-01-15T10:12:30Z",
      final_step: 5,
      action_count: 5,
      prompt: "Process the customer data CSV file by cleaning, transforming, and validating it",
      total_actions: 5
    },
    graph: {
      nodes: [
        { id: "prompt-1", type: "prompt", label: "Process customer data CSV" },
        { id: "step-1-1", type: "action", label: "file_reader: Load Data" },
        { id: "step-1-2", type: "action", label: "data_cleaner: Clean Data" },
        { id: "step-1-3", type: "action", label: "transformer: Transform" },
        { id: "step-1-4", type: "action", label: "validator: Validate" },
        { id: "step-1-5", type: "action", label: "file_writer: Save Results" }
      ],
      edges: [
        { id: "edge-start-1", source: "prompt-1", target: "step-1-1", type: "starts" },
        { id: "edge-1-2", source: "step-1-1", target: "step-1-2", type: "next" },
        { id: "edge-2-3", source: "step-1-2", target: "step-1-3", type: "next" },
        { id: "edge-3-4", source: "step-1-3", target: "step-1-4", type: "next" },
        { id: "edge-4-5", source: "step-1-4", target: "step-1-5", type: "next" },
        { id: "dep-2-1", source: "step-1-2", target: "step-1-1", type: "depends_on" },
        { id: "dep-3-2", source: "step-1-3", target: "step-1-2", type: "depends_on" },
        { id: "dep-4-3", source: "step-1-4", target: "step-1-3", type: "depends_on" },
        { id: "dep-5-4", source: "step-1-5", target: "step-1-4", type: "depends_on" }
      ]
    }
  },
  {
    id: "workflow-2",
    name: "AI Model Training",
    steps: [
      {
        id: "step-2-1",
        name: "Prepare Dataset",
        tool: "dataset_loader",
        description: "Load and split training data",
        inputs: '{"dataset_path": "ml_data/training.csv", "test_split": 0.2}',
        output: "dataset_prepared",
        sequence: 0
      },
      {
        id: "step-2-2",
        name: "Feature Engineering",
        tool: "feature_extractor",
        description: "Extract and select relevant features",
        inputs: '{"dataset": "dataset_prepared"}',
        output: "features_extracted",
        sequence: 1,
        dependencies: [{ id: "step-2-1", tool: "dataset_loader", action: "Prepare Dataset", output: "dataset_prepared" }]
      },
      {
        id: "step-2-3",
        name: "Train Model",
        tool: "ml_trainer",
        description: "Train machine learning model",
        inputs: '{"features": "features_extracted", "model_type": "random_forest"}',
        output: "trained_model",
        sequence: 2,
        dependencies: [{ id: "step-2-2", tool: "feature_extractor", action: "Feature Engineering", output: "features_extracted" }]
      },
      {
        id: "step-2-4",
        name: "Evaluate",
        tool: "evaluator",
        description: "Test model performance",
        inputs: '{"model": "trained_model", "test_data": "dataset_prepared"}',
        output: "evaluation_results",
        sequence: 3,
        dependencies: [
          { id: "step-2-3", tool: "ml_trainer", action: "Train Model", output: "trained_model" },
          { id: "step-2-1", tool: "dataset_loader", action: "Prepare Dataset", output: "dataset_prepared" }
        ]
      }
    ],
    metadata: {
      status: "completed",
      created_at: "2024-01-16T09:30:00Z",
      completed_at: "2024-01-16T11:45:15Z",
      final_step: 4,
      action_count: 4,
      prompt: "Train a machine learning model to predict customer churn using the provided dataset",
      total_actions: 4
    },
    graph: {
      nodes: [
        { id: "prompt-2", type: "prompt", label: "Train ML model for customer churn" },
        { id: "step-2-1", type: "action", label: "dataset_loader: Prepare Dataset" },
        { id: "step-2-2", type: "action", label: "feature_extractor: Feature Engineering" },
        { id: "step-2-3", type: "action", label: "ml_trainer: Train Model" },
        { id: "step-2-4", type: "action", label: "evaluator: Evaluate" }
      ],
      edges: [
        { id: "edge-start-2", source: "prompt-2", target: "step-2-1", type: "starts" },
        { id: "edge-2-1-2", source: "step-2-1", target: "step-2-2", type: "next" },
        { id: "edge-2-2-3", source: "step-2-2", target: "step-2-3", type: "next" },
        { id: "edge-2-3-4", source: "step-2-3", target: "step-2-4", type: "next" },
        { id: "dep-2-2-1", source: "step-2-2", target: "step-2-1", type: "depends_on" },
        { id: "dep-2-3-2", source: "step-2-3", target: "step-2-2", type: "depends_on" },
        { id: "dep-2-4-3", source: "step-2-4", target: "step-2-3", type: "depends_on" },
        { id: "dep-2-4-1", source: "step-2-4", target: "step-2-1", type: "depends_on" }
      ]
    }
  },
  {
    id: "workflow-3",
    name: "API Integration",
    steps: [
      {
        id: "step-3-1",
        name: "Authenticate",
        tool: "auth_handler",
        description: "Handle API authentication",
        inputs: '{"api_key": "$API_KEY", "endpoint": "https://api.example.com"}',
        output: "auth_token",
        sequence: 0
      },
      {
        id: "step-3-2",
        name: "Fetch Data",
        tool: "api_client",
        description: "Retrieve data from external API",
        inputs: '{"token": "auth_token", "endpoint": "/api/data"}',
        output: "api_data",
        sequence: 1,
        dependencies: [{ id: "step-3-1", tool: "auth_handler", action: "Authenticate", output: "auth_token" }]
      },
      {
        id: "step-3-3",
        name: "Process Response",
        tool: "response_processor",
        description: "Parse and validate API response",
        inputs: '{"data": "api_data"}',
        output: "processed_data",
        sequence: 2,
        dependencies: [{ id: "step-3-2", tool: "api_client", action: "Fetch Data", output: "api_data" }]
      }
    ],
    metadata: {
      status: "completed",
      created_at: "2024-01-17T14:15:00Z",
      completed_at: "2024-01-17T14:18:45Z",
      final_step: 3,
      action_count: 3,
      prompt: "Integrate with the customer API to fetch and process user data",
      total_actions: 3
    },
    graph: {
      nodes: [
        { id: "prompt-3", type: "prompt", label: "Integrate with customer API" },
        { id: "step-3-1", type: "action", label: "auth_handler: Authenticate" },
        { id: "step-3-2", type: "action", label: "api_client: Fetch Data" },
        { id: "step-3-3", type: "action", label: "response_processor: Process Response" }
      ],
      edges: [
        { id: "edge-start-3", source: "prompt-3", target: "step-3-1", type: "starts" },
        { id: "edge-3-1-2", source: "step-3-1", target: "step-3-2", type: "next" },
        { id: "edge-3-2-3", source: "step-3-2", target: "step-3-3", type: "next" },
        { id: "dep-3-2-1", source: "step-3-2", target: "step-3-1", type: "depends_on" },
        { id: "dep-3-3-2", source: "step-3-3", target: "step-3-2", type: "depends_on" }
      ]
    }
  },
  {
    id: "workflow-4",
    name: "Python File Creation",
    steps: [
      {
        id: "step-4-1",
        name: "create",
        tool: "file_tool",
        description: "Create a new Python file",
        inputs: '{"filename": "hello.py"}',
        output: "file_created",
        sequence: 0
      },
      {
        id: "step-4-2",
        name: "write",
        tool: "text_tool",
        description: "Add hello function to the file",
        inputs: '{"file": "file_created", "content": "def hello():\\n    print(\\"Hello World\\")"}',
        output: "hello_function_added",
        sequence: 1,
        dependencies: [{ id: "step-4-1", tool: "file_tool", action: "create", output: "file_created" }]
      },
      {
        id: "step-4-3",
        name: "write",
        tool: "text_tool",
        description: "Add goodbye function to the file",
        inputs: '{"file": "file_created", "content": "def goodbye():\\n    print(\\"Goodbye!\\")"}',
        output: "goodbye_function_added",
        sequence: 2,
        dependencies: [{ id: "step-4-1", tool: "file_tool", action: "create", output: "file_created" }]
      }
    ],
    metadata: {
      status: "completed",
      created_at: "2024-01-18T16:20:00Z",
      completed_at: "2024-01-18T16:22:10Z",
      final_step: 3,
      action_count: 3,
      prompt: "Create a Python file and add some functions to it",
      total_actions: 3
    },
    graph: {
      nodes: [
        { id: "prompt-4", type: "prompt", label: "Create Python file with functions" },
        { id: "step-4-1", type: "action", label: "file_tool: create" },
        { id: "step-4-2", type: "action", label: "text_tool: write hello" },
        { id: "step-4-3", type: "action", label: "text_tool: write goodbye" }
      ],
      edges: [
        { id: "edge-start-4", source: "prompt-4", target: "step-4-1", type: "starts" },
        { id: "edge-4-1-2", source: "step-4-1", target: "step-4-2", type: "next" },
        { id: "edge-4-2-3", source: "step-4-2", target: "step-4-3", type: "next" },
        { id: "dep-4-2-1", source: "step-4-2", target: "step-4-1", type: "depends_on" },
        { id: "dep-4-3-1", source: "step-4-3", target: "step-4-1", type: "depends_on" }
      ]
    }
  },
  {
    id: "workflow-5",
    name: "Report Generation",
    steps: [
      {
        id: "step-5-1",
        name: "collect_data",
        tool: "data_collector",
        description: "Collect data from multiple sources",
        inputs: '{"sources": ["database", "api", "files"]}',
        output: "collected_data",
        sequence: 0
      },
      {
        id: "step-5-2",
        name: "analyze",
        tool: "analyzer",
        description: "Analyze collected data for insights",
        inputs: '{"data": "collected_data"}',
        output: "analysis_results",
        sequence: 1,
        dependencies: [{ id: "step-5-1", tool: "data_collector", action: "collect_data", output: "collected_data" }]
      },
      {
        id: "step-5-3",
        name: "generate_charts",
        tool: "chart_generator",
        description: "Create visualizations from analysis",
        inputs: '{"analysis": "analysis_results"}',
        output: "charts_created",
        sequence: 2,
        dependencies: [{ id: "step-5-2", tool: "analyzer", action: "analyze", output: "analysis_results" }]
      },
      {
        id: "step-5-4",
        name: "create_report",
        tool: "report_builder",
        description: "Compile final report with charts and analysis",
        inputs: '{"analysis": "analysis_results", "charts": "charts_created"}',
        output: "final_report",
        sequence: 3,
        dependencies: [
          { id: "step-5-2", tool: "analyzer", action: "analyze", output: "analysis_results" },
          { id: "step-5-3", tool: "chart_generator", action: "generate_charts", output: "charts_created" }
        ]
      }
    ],
    metadata: {
      status: "completed",
      created_at: "2024-01-19T08:45:00Z",
      completed_at: "2024-01-19T09:30:20Z",
      final_step: 4,
      action_count: 4,
      prompt: "Generate a comprehensive business report with data analysis and visualizations",
      total_actions: 4
    },
    graph: {
      nodes: [
        { id: "prompt-5", type: "prompt", label: "Generate business report" },
        { id: "step-5-1", type: "action", label: "data_collector: collect_data" },
        { id: "step-5-2", type: "action", label: "analyzer: analyze" },
        { id: "step-5-3", type: "action", label: "chart_generator: generate_charts" },
        { id: "step-5-4", type: "action", label: "report_builder: create_report" }
      ],
      edges: [
        { id: "edge-start-5", source: "prompt-5", target: "step-5-1", type: "starts" },
        { id: "edge-5-1-2", source: "step-5-1", target: "step-5-2", type: "next" },
        { id: "edge-5-2-3", source: "step-5-2", target: "step-5-3", type: "next" },
        { id: "edge-5-3-4", source: "step-5-3", target: "step-5-4", type: "next" },
        { id: "dep-5-2-1", source: "step-5-2", target: "step-5-1", type: "depends_on" },
        { id: "dep-5-3-2", source: "step-5-3", target: "step-5-2", type: "depends_on" },
        { id: "dep-5-4-2", source: "step-5-4", target: "step-5-2", type: "depends_on" },
        { id: "dep-5-4-3", source: "step-5-4", target: "step-5-3", type: "depends_on" }
      ]
    }
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

