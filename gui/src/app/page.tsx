import React, { useState } from "react";
import { ChatWindow } from "@/components/chat";
import { useChatSessionsApi } from "@/hooks/useApiWithFallback";
import { type MockChatMessage } from "@/data/mock-data";
import { defaultChatResponse } from "@/data/mock-data";

export default function Page() {
  const { data: chatSessions = [], isLoading } = useChatSessionsApi();
  const [currentMessages, setCurrentMessages] = useState<MockChatMessage[]>(() => {
    // Start with the first session's messages or empty
    return chatSessions[0]?.messages || [];
  });

  const handleSendMessage = (messageContent: string) => {
    const userMessage: MockChatMessage = {
      id: `msg-${Date.now()}`,
      role: "user",
      content: messageContent,
      timestamp: new Date(),
    };

    setCurrentMessages(prev => [...prev, userMessage]);

    // Simulate assistant response
    setTimeout(() => {
      const assistantMessage: MockChatMessage = {
        id: `msg-${Date.now()}-assistant`,
        role: "assistant",
        content: defaultChatResponse,
        timestamp: new Date(),
      };
      setCurrentMessages(prev => [...prev, assistantMessage]);
    }, 1000);
  };

  // Use messages from first session if available, otherwise start fresh
  const messagesToShow = currentMessages.length > 0 ? currentMessages : (chatSessions[0]?.messages || []);

  return (
    <div className="flex flex-1 flex-col gap-4 p-4 pt-0 h-full">
      <div className="flex-1 bg-muted/50 rounded-xl overflow-hidden">
        <ChatWindow
          messages={messagesToShow}
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          className="h-full"
        />
      </div>
    </div>
  );
}
