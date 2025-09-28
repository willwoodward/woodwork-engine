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