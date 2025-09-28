import React, { useRef, useEffect } from "react";
import { ChatMessage } from "./chat-message";
import { ChatInput } from "./chat-input";
import { EmptyState } from "@/components/ui";
import { type MockChatMessage } from "@/data/mock-data";

interface ChatWindowProps {
  messages: MockChatMessage[];
  onSendMessage: (message: string) => void;
  isLoading?: boolean;
  className?: string;
}

export const ChatWindow = ({
  messages,
  onSendMessage,
  isLoading = false,
  className = "",
}: ChatWindowProps) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Messages Area */}
      <div className="flex-1 overflow-auto">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <EmptyState message="Start a conversation by typing a message below" />
          </div>
        ) : (
          <div className="space-y-4 p-4">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {isLoading && (
              <div className="flex gap-3 p-4">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-muted text-muted-foreground flex items-center justify-center">
                  <div className="w-2 h-2 bg-current rounded-full animate-pulse" />
                </div>
                <div className="flex-1">
                  <div className="text-sm text-muted-foreground">Assistant is typing...</div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t bg-background p-4">
        <ChatInput
          onSendMessage={onSendMessage}
          disabled={isLoading}
          placeholder="Ask about workflows, data processing, or anything else..."
        />
      </div>
    </div>
  );
};