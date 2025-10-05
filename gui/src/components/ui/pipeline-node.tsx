import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface PipelineNodeProps {
  icon: LucideIcon;
  label: string;
  count?: number;
  variant?: "hook" | "pipe" | "event";
  className?: string;
}

export function PipelineNode({
  icon: Icon,
  label,
  count,
  variant = "event",
  className,
}: PipelineNodeProps) {
  const variantStyles = {
    hook: "bg-blue-500/10 border-blue-500/30 text-blue-600 dark:text-blue-400",
    pipe: "bg-purple-500/10 border-purple-500/30 text-purple-600 dark:text-purple-400",
    event: "bg-gray-500/10 border-gray-500/30 text-gray-600 dark:text-gray-400",
  };

  return (
    <div
      className={cn(
        "flex items-center gap-3 px-4 py-3 rounded-lg border-2 bg-card min-w-[180px] transition-all hover:shadow-md",
        variantStyles[variant],
        className
      )}
    >
      <Icon className="w-5 h-5 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="font-medium text-sm truncate">{label}</div>
        {count !== undefined && (
          <div className="text-xs opacity-70">{count} listener{count !== 1 ? 's' : ''}</div>
        )}
      </div>
    </div>
  );
}
