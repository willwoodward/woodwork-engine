import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Lightbulb, Layers, Sparkles, Check, X } from "lucide-react";
import type { Suggestion } from "@/types/task";

interface SuggestionCardProps {
  suggestion: Suggestion;
  onAccept?: (id: string) => void;
  onReject?: (id: string) => void;
}

const suggestionConfig = {
  workflow: {
    icon: Layers,
    color: "bg-purple-500/10 text-purple-500 border-purple-500/20",
    label: "Workflow",
  },
  optimization: {
    icon: Sparkles,
    color: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    label: "Optimization",
  },
  batching: {
    icon: Lightbulb,
    color: "bg-green-500/10 text-green-500 border-green-500/20",
    label: "Batching",
  },
};

export function SuggestionCard({ suggestion, onAccept, onReject }: SuggestionCardProps) {
  const config = suggestionConfig[suggestion.type];
  const Icon = config.icon;

  return (
    <Card className={suggestion.accepted ? "border-green-500/50 bg-green-500/5" : ""}>
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-3">
        <div className="space-y-2 flex-1">
          <Badge variant="outline" className={config.color}>
            <Icon className="h-3 w-3 mr-1" />
            {config.label}
          </Badge>
          <CardTitle className="text-lg">{suggestion.title}</CardTitle>
        </div>
        {suggestion.accepted && (
          <Badge variant="default" className="bg-green-500">
            <Check className="h-3 w-3 mr-1" />
            Accepted
          </Badge>
        )}
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">{suggestion.description}</p>
        {suggestion.relatedTasks && suggestion.relatedTasks.length > 0 && (
          <p className="text-xs text-muted-foreground mt-3">
            Based on {suggestion.relatedTasks.length} task
            {suggestion.relatedTasks.length !== 1 ? "s" : ""}
          </p>
        )}
      </CardContent>
      {!suggestion.accepted && (onAccept || onReject) && (
        <CardFooter className="flex gap-2">
          {onAccept && (
            <Button
              size="sm"
              onClick={() => onAccept(suggestion.id)}
              className="flex-1"
            >
              <Check className="h-4 w-4 mr-1" />
              Accept
            </Button>
          )}
          {onReject && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => onReject(suggestion.id)}
              className="flex-1"
            >
              <X className="h-4 w-4 mr-1" />
              Dismiss
            </Button>
          )}
        </CardFooter>
      )}
    </Card>
  );
}
