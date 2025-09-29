
import { Clock, AlertCircle, Bot, FileEdit, Shield, HelpCircle, MessageSquare } from "lucide-react";
import { Badge, IconBadge } from "@/components/ui";
import { getPriorityVariant, getStatusVariant, formatPriority, formatStatus } from "@/lib/badge-utils";
import { type MockHumanInputRequest } from "@/data/mock-data";

interface RequestListItemProps {
  request: MockHumanInputRequest;
  isSelected?: boolean;
  onClick: () => void;
}

const typeIcons = {
  approval: Shield,
  edit_content: FileEdit,
  confirmation: HelpCircle,
  choice: AlertCircle,
  ask_user: MessageSquare,
};

export const RequestListItem = ({ request, isSelected = false, onClick }: RequestListItemProps) => {
  const TypeIcon = typeIcons[request.type];
  const isPending = request.status === 'pending';

  return (
    <div
      onClick={onClick}
      className={`p-4 border-b cursor-pointer transition-all hover:bg-accent/50 ${
        isSelected ? "bg-primary/5 border-l-4 border-l-primary" : ""
      } ${isPending ? "bg-background" : "bg-muted/30"}`}
    >
      <div className="flex items-start gap-3">
        {/* Type Icon */}
        <IconBadge
          icon={TypeIcon}
          variant={getPriorityVariant(request.priority)}
        />

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <h4 className={`font-medium text-sm truncate ${isPending ? "text-foreground" : "text-muted-foreground"}`}>
              {request.title}
            </h4>
            <div className="flex items-center gap-2 flex-shrink-0">
              {/* Priority Badge */}
              <Badge variant={getPriorityVariant(request.priority)}>
                {formatPriority(request.priority)}
              </Badge>
              {/* Status Badge */}
              <Badge variant={getStatusVariant(request.status)}>
                {formatStatus(request.status)}
              </Badge>
            </div>
          </div>

          <p className="text-xs text-muted-foreground mb-2 line-clamp-2">
            {request.description}
          </p>

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <div className="flex items-center gap-1">
              <Bot className="w-3 h-3" />
              <span>{request.agentName}</span>
              {request.workflowName && (
                <>
                  <span>•</span>
                  <span>{request.workflowName}</span>
                </>
              )}
            </div>
            <div className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              <span>{request.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};