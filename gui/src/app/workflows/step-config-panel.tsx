import React, { useState, useEffect } from "react";
import { Settings2 } from "lucide-react";
import { type MockWorkflowStep } from "@/data/mock-workflows";
import { SidebarSection, InfoDisplay, EmptyState, ToolIcon } from "@/components/ui";

interface StepConfigPanelProps {
  step: MockWorkflowStep | null;
  onUpdateStep: (step: MockWorkflowStep) => void;
}

export default function StepConfigPanel({ step, onUpdateStep }: StepConfigPanelProps) {
  const [localStep, setLocalStep] = useState<MockWorkflowStep | null>(null);

  // Update local state when step changes
  useEffect(() => {
    setLocalStep(step ? { ...step } : null);
  }, [step]);

  const handleChange = (field: keyof MockWorkflowStep, value: string) => {
    if (!localStep) return;

    const updatedStep = { ...localStep, [field]: value };
    setLocalStep(updatedStep);
    onUpdateStep(updatedStep);
  };

  if (!step || !localStep) {
    return (
      <div className="h-full flex flex-col">
        <div className="flex items-center gap-2 mb-4">
          <Settings2 className="w-4 h-4" />
          <h3 className="font-semibold">Step Configuration</h3>
        </div>
        <EmptyState message="Select a step to configure its properties" />
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2 mb-4">
        <Settings2 className="w-4 h-4" />
        <h3 className="font-semibold">Step Configuration</h3>
      </div>

      <div className="flex-1 overflow-auto space-y-4">
        {/* Step Info */}
        <SidebarSection title="Step Info">
          <div className="flex items-center gap-2 mb-3">
            <ToolIcon tool={localStep.tool} className="w-5 h-5 text-muted-foreground" />
            <span className="text-sm font-medium">{localStep.tool}</span>
          </div>
          <InfoDisplay
            items={[
              { key: "Tool Type", value: localStep.tool },
            ]}
          />
        </SidebarSection>

        {/* Basic Properties */}
        <SidebarSection title="Properties">
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium text-muted-foreground mb-1 block">
                Step Name
              </label>
              <input
                type="text"
                value={localStep.name}
                onChange={(e) => handleChange("name", e.target.value)}
                className="w-full px-3 py-2 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="Enter step name"
              />
            </div>

            <div>
              <label className="text-sm font-medium text-muted-foreground mb-1 block">
                Description
              </label>
              <textarea
                value={localStep.description}
                onChange={(e) => handleChange("description", e.target.value)}
                className="w-full px-3 py-2 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                rows={3}
                placeholder="Describe what this step does"
              />
            </div>
          </div>
        </SidebarSection>

        {/* Tool-specific Configuration */}
        <SidebarSection title="Tool Configuration">
          <div className="space-y-3">
            {getToolSpecificConfig(localStep.tool).map((config) => (
              <div key={config.key}>
                <label className="text-sm font-medium text-muted-foreground mb-1 block">
                  {config.label}
                </label>
                {config.type === "select" ? (
                  <select className="w-full px-3 py-2 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary">
                    <option value="">{config.placeholder}</option>
                    {config.options?.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type={config.type}
                    className="w-full px-3 py-2 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary"
                    placeholder={config.placeholder}
                  />
                )}
              </div>
            ))}
          </div>
        </SidebarSection>

        {/* Advanced Settings */}
        <SidebarSection title="Advanced">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm">Skip on Error</span>
              <input
                type="checkbox"
                className="rounded border-border focus:ring-2 focus:ring-primary"
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Enable Logging</span>
              <input
                type="checkbox"
                defaultChecked
                className="rounded border-border focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground mb-1 block">
                Timeout (seconds)
              </label>
              <input
                type="number"
                defaultValue={30}
                className="w-full px-3 py-2 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          </div>
        </SidebarSection>
      </div>
    </div>
  );
}

// Helper function to get tool-specific configuration options
function getToolSpecificConfig(tool: string) {
  const configs: Record<string, Array<{
    key: string;
    label: string;
    type: string;
    placeholder: string;
    options?: string[];
  }>> = {
    file_reader: [
      { key: "file_path", label: "File Path", type: "text", placeholder: "/path/to/file.csv" },
      { key: "format", label: "File Format", type: "select", placeholder: "Select format", options: ["CSV", "JSON", "XML", "Excel"] },
    ],
    data_cleaner: [
      { key: "remove_duplicates", label: "Remove Duplicates", type: "checkbox", placeholder: "" },
      { key: "handle_missing", label: "Missing Value Strategy", type: "select", placeholder: "Select strategy", options: ["Drop", "Fill", "Interpolate"] },
    ],
    transformer: [
      { key: "transformation", label: "Transformation Type", type: "select", placeholder: "Select transformation", options: ["Normalize", "Scale", "Encode", "Custom"] },
    ],
    validator: [
      { key: "rules", label: "Validation Rules", type: "text", placeholder: "Enter validation rules" },
    ],
    file_writer: [
      { key: "output_path", label: "Output Path", type: "text", placeholder: "/path/to/output.csv" },
      { key: "format", label: "Output Format", type: "select", placeholder: "Select format", options: ["CSV", "JSON", "XML", "Excel"] },
    ],
    dataset_loader: [
      { key: "dataset_path", label: "Dataset Path", type: "text", placeholder: "/path/to/dataset" },
      { key: "split_ratio", label: "Train/Test Split", type: "number", placeholder: "0.8" },
    ],
    feature_extractor: [
      { key: "features", label: "Feature Columns", type: "text", placeholder: "col1,col2,col3" },
      { key: "method", label: "Extraction Method", type: "select", placeholder: "Select method", options: ["PCA", "LDA", "Manual"] },
    ],
    ml_trainer: [
      { key: "algorithm", label: "Algorithm", type: "select", placeholder: "Select algorithm", options: ["Random Forest", "SVM", "Neural Network", "XGBoost"] },
      { key: "hyperparameters", label: "Hyperparameters", type: "text", placeholder: "JSON format" },
    ],
    evaluator: [
      { key: "metrics", label: "Evaluation Metrics", type: "select", placeholder: "Select metrics", options: ["Accuracy", "Precision", "Recall", "F1-Score", "ROC-AUC"] },
    ],
    auth_handler: [
      { key: "auth_type", label: "Authentication Type", type: "select", placeholder: "Select type", options: ["API Key", "OAuth", "Bearer Token", "Basic Auth"] },
      { key: "credentials", label: "Credentials", type: "password", placeholder: "Enter credentials" },
    ],
    api_client: [
      { key: "endpoint", label: "API Endpoint", type: "text", placeholder: "https://api.example.com" },
      { key: "method", label: "HTTP Method", type: "select", placeholder: "Select method", options: ["GET", "POST", "PUT", "DELETE"] },
    ],
    response_processor: [
      { key: "response_format", label: "Response Format", type: "select", placeholder: "Select format", options: ["JSON", "XML", "Text", "Binary"] },
      { key: "extraction_path", label: "Data Extraction Path", type: "text", placeholder: "$.data.items" },
    ],
  };

  return configs[tool] || [];
}