import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Plus, ArrowUp } from "lucide-react";

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

export const ChatInput = ({
  onSendMessage,
  placeholder = "Type your message...",
  disabled = false,
  className = "",
}: ChatInputProps) => {
  const [message, setMessage] = useState("");

  const handleSend = () => {
    if (message.trim() && !disabled) {
      onSendMessage(message.trim());
      setMessage("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={`bg-muted/50 rounded-2xl p-4 border ${className}`}>
      <div className="flex gap-3 items-end">
        {/* Attachment Button */}
        <Button
          variant="outline"
          size="icon"
          className="flex-shrink-0"
          disabled={disabled}
        >
          <Plus className="w-4 h-4" />
        </Button>

        {/* Message Input */}
        <div className="flex-1">
          <Textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            className="min-h-[2.5rem] max-h-32 resize-none border-none bg-transparent focus:ring-0 focus:border-none"
            rows={1}
          />
        </div>

        {/* Send Button */}
        <Button
          onClick={handleSend}
          disabled={disabled || !message.trim()}
          size="icon"
          className="flex-shrink-0"
        >
          <ArrowUp className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
};