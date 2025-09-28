import {
  FileText,
  Wrench,
  Shuffle,
  CheckCircle,
  Save,
  Database,
  Brain,
  BarChart3,
  Key,
  Download,
  Settings,
  Code,
} from "lucide-react";

// Function to get the appropriate icon for each tool type
export const getToolIcon = (tool: string) => {
  const iconMap: Record<string, any> = {
    file_reader: FileText,
    data_cleaner: Wrench,
    transformer: Shuffle,
    validator: CheckCircle,
    file_writer: Save,
    dataset_loader: Database,
    feature_extractor: BarChart3,
    ml_trainer: Brain,
    evaluator: BarChart3,
    auth_handler: Key,
    api_client: Download,
    response_processor: Settings,
  };

  return iconMap[tool] || Code;
};

interface ToolIconProps {
  tool: string;
  className?: string;
}

export const ToolIcon = ({ tool, className = "w-4 h-4" }: ToolIconProps) => {
  const IconComponent = getToolIcon(tool);
  return <IconComponent className={className} />;
};