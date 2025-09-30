
import { Calendar, Clock, CheckCircle } from "lucide-react";

interface WorkflowMetadata {
  created_at?: string;
  completed_at?: string;
  final_step?: number;
  action_count?: number;
  status?: string;
}

interface WorkflowCardProps {
  id: string;
  name: string;
  stepCount: number;
  metadata?: WorkflowMetadata;
  onClick?: () => void;
  className?: string;
}

export const WorkflowCard = ({ id, name, stepCount, metadata, onClick, className = "" }: WorkflowCardProps) => {
  const formatDate = (dateStr?: string) => {
    if (!dateStr) return null;
    try {
      return new Date(dateStr).toLocaleDateString();
    } catch {
      return dateStr;
    }
  };

  const isCompleted = metadata?.status === 'completed';

  return (
    <div
      className={`p-3 rounded-lg bg-card border hover:bg-accent transition-colors cursor-pointer ${className}`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between">
        <div className="font-medium text-card-foreground flex-1 pr-2">{name || id}</div>
        {isCompleted && <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />}
      </div>

      <div className="text-xs text-muted-foreground mt-1">
        {stepCount} step{stepCount !== 1 ? 's' : ''}
        {metadata?.action_count && metadata.action_count !== stepCount && (
          <span> • {metadata.action_count} actions</span>
        )}
      </div>

      {metadata && (
        <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
          {metadata.completed_at && (
            <div className="flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              <span>{formatDate(metadata.completed_at)}</span>
            </div>
          )}
          {metadata.created_at && !metadata.completed_at && (
            <div className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              <span>{formatDate(metadata.created_at)}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};