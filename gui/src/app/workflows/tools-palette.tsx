import { ToolIcon } from "@/components/ui";

const availableTools = [
  { id: "file_reader", name: "File Reader", description: "Read data from files" },
  { id: "data_cleaner", name: "Data Cleaner", description: "Clean and preprocess data" },
  { id: "transformer", name: "Transformer", description: "Transform data structure" },
  { id: "validator", name: "Validator", description: "Validate data quality" },
  { id: "file_writer", name: "File Writer", description: "Write data to files" },
  { id: "dataset_loader", name: "Dataset Loader", description: "Load training datasets" },
  { id: "feature_extractor", name: "Feature Extractor", description: "Extract features from data" },
  { id: "ml_trainer", name: "ML Trainer", description: "Train machine learning models" },
  { id: "evaluator", name: "Evaluator", description: "Evaluate model performance" },
  { id: "auth_handler", name: "Auth Handler", description: "Handle authentication" },
  { id: "api_client", name: "API Client", description: "Make API calls" },
  { id: "response_processor", name: "Response Processor", description: "Process API responses" },
];

const toolCategories = [
  {
    name: "Data Processing",
    tools: ["file_reader", "data_cleaner", "transformer", "validator", "file_writer"],
  },
  {
    name: "Machine Learning",
    tools: ["dataset_loader", "feature_extractor", "ml_trainer", "evaluator"],
  },
  {
    name: "API Integration",
    tools: ["auth_handler", "api_client", "response_processor"],
  },
];

interface ToolsPaletteProps {
  onAddStep: (tool: string) => void;
}

export default function ToolsPalette({ onAddStep }: ToolsPaletteProps) {
  return (
    <div className="h-full flex flex-col">
      <h3 className="font-semibold mb-4">Tools</h3>

      <div className="flex-1 overflow-auto space-y-4">
        {toolCategories.map((category) => (
          <div key={category.name}>
            <h4 className="text-sm font-medium text-muted-foreground mb-2 uppercase tracking-wide">
              {category.name}
            </h4>
            <div className="space-y-1">
              {category.tools.map((toolId) => {
                const tool = availableTools.find(t => t.id === toolId);
                if (!tool) return null;

                return (
                  <div
                    key={tool.id}
                    onClick={() => onAddStep(tool.id)}
                    className="p-2 rounded border border-dashed border-border hover:border-primary hover:bg-primary/5 cursor-pointer transition-all group"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <ToolIcon
                        tool={tool.id}
                        className="w-4 h-4 text-muted-foreground group-hover:text-primary"
                      />
                      <span className="text-sm font-medium group-hover:text-primary">
                        {tool.name}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {tool.description}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}