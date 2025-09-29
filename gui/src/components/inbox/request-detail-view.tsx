import { useState } from "react";
import { Check, X, Clock, Bot, Play, Edit3, Copy, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { SidebarSection, Badge } from "@/components/ui";
import { getPriorityVariant, getStatusVariant, formatPriority, formatStatus } from "@/lib/badge-utils";
import { type MockHumanInputRequest } from "@/data/mock-data";

interface RequestDetailViewProps {
  request: MockHumanInputRequest;
  onApprove?: (id: string) => void;
  onReject?: (id: string) => void;
  onUpdateContent?: (id: string, content: string) => void;
  onSelectChoice?: (id: string, choice: string) => void;
  onRespondToQuestion?: (id: string, response: string) => void;
}

export const RequestDetailView = ({
  request,
  onApprove,
  onReject,
  onUpdateContent,
  onSelectChoice,
  onRespondToQuestion,
}: RequestDetailViewProps) => {
  const [editedContent, setEditedContent] = useState(request.content || "");
  const [selectedChoice, setSelectedChoice] = useState<string>("");
  const [userResponse, setUserResponse] = useState<string>("");

  const isPending = request.status === 'pending';

  const handleApprove = () => {
    if (request.type === 'edit_content' && onUpdateContent) {
      onUpdateContent(request.id, editedContent);
    } else if (request.type === 'choice' && onSelectChoice && selectedChoice) {
      onSelectChoice(request.id, selectedChoice);
    } else if (request.type === 'ask_user' && onRespondToQuestion) {
      onRespondToQuestion(request.id, userResponse);
    } else if (onApprove) {
      onApprove(request.id);
    }
  };

  const handleReject = () => {
    if (onReject) {
      onReject(request.id);
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="border-b p-4 bg-card">
        <div className="flex items-start justify-between mb-3">
          <h2 className="text-lg font-semibold">{request.title}</h2>
          <div className="flex items-center gap-2">
            <Badge variant={getPriorityVariant(request.priority)}>
              {formatPriority(request.priority)} priority
            </Badge>
            <Badge variant={getStatusVariant(request.status)}>
              {formatStatus(request.status)}
            </Badge>
          </div>
        </div>

        <p className="text-muted-foreground mb-3">{request.description}</p>

        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <div className="flex items-center gap-1">
            <Bot className="w-4 h-4" />
            <span>{request.agentName}</span>
          </div>
          {request.workflowName && (
            <div className="flex items-center gap-1">
              <Play className="w-4 h-4" />
              <span>{request.workflowName}</span>
            </div>
          )}
          <div className="flex items-center gap-1">
            <Clock className="w-4 h-4" />
            <span>{request.timestamp.toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {/* Context Information */}
        {request.metadata?.context && (
          <SidebarSection title="Context">
            <p className="text-sm text-muted-foreground">{request.metadata.context}</p>
          </SidebarSection>
        )}

        {/* Command Information */}
        {request.metadata?.command && (
          <SidebarSection title="Command">
            <div className="bg-muted/50 rounded-lg p-3 font-mono text-sm">
              <div className="flex items-center justify-between mb-2">
                <span className="text-muted-foreground">Command to execute:</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigator.clipboard.writeText(request.metadata?.command || "")}
                >
                  <Copy className="w-3 h-3" />
                </Button>
              </div>
              <code className="text-foreground">{request.metadata.command}</code>
            </div>
          </SidebarSection>
        )}

        {/* Editable Content */}
        {request.type === 'edit_content' && (
          <SidebarSection title="Content">
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Edit3 className="w-4 h-4" />
                <span className="text-sm font-medium">Edit the content below:</span>
              </div>
              <Textarea
                value={editedContent}
                onChange={(e) => setEditedContent(e.target.value)}
                className="min-h-[200px] font-mono text-sm"
                disabled={!isPending}
              />
              {request.originalContent && editedContent !== request.originalContent && (
                <div className="text-xs text-muted-foreground">
                  Content has been modified from the original.
                </div>
              )}
            </div>
          </SidebarSection>
        )}

        {/* Choice Selection */}
        {request.type === 'choice' && request.metadata?.options && (
          <SidebarSection title="Choose an Option">
            <div className="space-y-2">
              {request.metadata.options.map((option, index) => (
                <label
                  key={index}
                  className={`flex items-center p-3 border rounded-lg cursor-pointer transition-colors ${
                    selectedChoice === option
                      ? "border-primary bg-primary/5"
                      : "border-border hover:bg-accent"
                  }`}
                >
                  <input
                    type="radio"
                    name="choice"
                    value={option}
                    checked={selectedChoice === option}
                    onChange={(e) => setSelectedChoice(e.target.value)}
                    disabled={!isPending}
                    className="mr-3"
                  />
                  <span className="text-sm">{option}</span>
                </label>
              ))}
            </div>
          </SidebarSection>
        )}

        {/* User Input Response */}
        {request.type === 'ask_user' && (
          <SidebarSection title="Agent Question">
            <div className="space-y-4">
              {/* Display the question */}
              <div className="bg-muted/50 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <MessageSquare className="w-4 h-4 text-primary" />
                  <span className="text-sm font-medium">Question:</span>
                </div>
                <p className="text-sm">{request.metadata?.question || request.description}</p>
                {request.metadata?.timeout_seconds && (
                  <p className="text-xs text-muted-foreground mt-2">
                    Timeout: {request.metadata.timeout_seconds} seconds
                  </p>
                )}
              </div>

              {/* Response input */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Your Response:</label>
                <Textarea
                  value={userResponse}
                  onChange={(e) => setUserResponse(e.target.value)}
                  placeholder="Type your response here..."
                  className="min-h-[100px]"
                  disabled={!isPending}
                />
              </div>
            </div>
          </SidebarSection>
        )}
      </div>

      {/* Actions */}
      {isPending && (
        <div className="border-t p-4 bg-card">
          <div className="flex gap-3 justify-end">
            <Button
              variant="outline"
              onClick={handleReject}
              className="flex items-center gap-2"
            >
              <X className="w-4 h-4" />
              Reject
            </Button>
            <Button
              onClick={handleApprove}
              disabled={
                (request.type === 'choice' && !selectedChoice) ||
                (request.type === 'edit_content' && !editedContent.trim()) ||
                (request.type === 'ask_user' && !userResponse.trim())
              }
              className="flex items-center gap-2"
            >
              <Check className="w-4 h-4" />
              {request.type === 'edit_content' ? 'Save & Send' :
               request.type === 'choice' ? 'Select' :
               request.type === 'confirmation' ? 'Confirm' :
               request.type === 'ask_user' ? 'Send Response' :
               'Approve'}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};