import { ChatWindow } from "@/components/chat";
import { useChatAPI } from "@/hooks/useChatAPI";

export default function Page() {
  const {
    messages,
    sendMessage,
    isLoading,
    isConnected,
    sessionId,
    inputStatus,
    clearMessages
  } = useChatAPI();

  return (
    <div className="flex flex-1 flex-col gap-4 p-4 pt-0 h-full">
      {/* Connection status */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <div className={`w-2 h-2 rounded-full ${
          isConnected ? 'bg-green-500' : 'bg-red-500'
        }`} />
        {isConnected ? 'Connected to agent' : 'Disconnected'}
        {sessionId && (
          <span className="ml-2">Session: {sessionId.slice(0, 8)}...</span>
        )}
        {inputStatus && (
          <span className="ml-2">API Inputs: {inputStatus.api_inputs}</span>
        )}
        <button
          onClick={clearMessages}
          className="ml-auto text-xs bg-muted px-2 py-1 rounded hover:bg-muted/80"
        >
          Clear Chat
        </button>
      </div>

      <div className="flex-1 bg-muted/50 rounded-xl overflow-hidden">
        <ChatWindow
          messages={messages}
          onSendMessage={sendMessage}
          isLoading={isLoading}
          className="h-full"
        />
      </div>
    </div>
  );
}