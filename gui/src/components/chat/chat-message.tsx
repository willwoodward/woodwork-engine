import React from "react";
import { User, Bot } from "lucide-react";
import { type MockChatMessage } from "@/data/mock-data";

interface ChatMessageProps {
  message: MockChatMessage;
  className?: string;
}

export const ChatMessage = ({ message, className = "" }: ChatMessageProps) => {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-3 p-4 ${className}`}>
      {/* Avatar */}
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
        isUser
          ? "bg-primary text-primary-foreground"
          : "bg-muted text-muted-foreground"
      }`}>
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>

      {/* Message Content */}
      <div className="flex-1 space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">
            {isUser ? "You" : "Assistant"}
          </span>
          <span className="text-xs text-muted-foreground">
            {message.timestamp.toLocaleTimeString()}
          </span>
        </div>
        <div className="text-sm text-foreground whitespace-pre-wrap">
          {message.content}
        </div>
      </div>
    </div>
  );
};