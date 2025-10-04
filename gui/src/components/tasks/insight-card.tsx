import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, AlertCircle, Sparkles } from "lucide-react";

interface InsightCardProps {
  type: "repetition" | "bottleneck" | "optimization";
  title: string;
  description: string;
  taskCount?: number;
}

const insightConfig = {
  repetition: {
    icon: TrendingUp,
    color: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    label: "Repetition",
  },
  bottleneck: {
    icon: AlertCircle,
    color: "bg-orange-500/10 text-orange-500 border-orange-500/20",
    label: "Bottleneck",
  },
  optimization: {
    icon: Sparkles,
    color: "bg-purple-500/10 text-purple-500 border-purple-500/20",
    label: "Optimization",
  },
};

export function InsightCard({
  type,
  title,
  description,
  taskCount,
}: InsightCardProps) {
  const config = insightConfig[type];
  const Icon = config.icon;

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div className="space-y-1">
          <Badge variant="outline" className={config.color}>
            {config.label}
          </Badge>
          <CardTitle className="text-lg mt-2">{title}</CardTitle>
        </div>
        <Icon className="h-5 w-5 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">{description}</p>
        {taskCount && (
          <p className="text-xs text-muted-foreground mt-2">
            Based on {taskCount} similar task{taskCount !== 1 ? "s" : ""}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
