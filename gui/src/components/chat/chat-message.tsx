import { User, Bot } from "lucide-react";

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  type?: 'message' | 'event' | 'thought' | 'action' | 'error';
  thinking?: string[];
  isThinking?: boolean;
}

interface ChatMessageProps {
  message: ChatMessage;
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

        {/* Thinking indicators with connecting line */}
        {message.thinking && message.thinking.length > 0 && (
          <div className="relative mt-4">
            {/* Main connecting line from avatar */}
            <div className="absolute left-[-24px] top-2 w-4 h-2 border-l-2 border-b-2 border-muted-foreground/40 rounded-bl-md"></div>

            {/* Vertical line extending down for multiple thoughts */}
            {message.thinking.length > 1 && (
              <div
                className="absolute left-[-25px] top-2 w-0.5 bg-muted-foreground/30"
                style={{ height: `${(message.thinking.length - 1) * 3 + (message.isThinking ? 3 : 0) + 1.5}rem` }}
              ></div>
            )}

            {/* Thinking bubbles */}
            <div className="space-y-3">
              {message.thinking.map((thought, index) => (
                <div
                  key={index}
                  className="relative text-xs text-muted-foreground italic bg-muted/50 px-3 py-2 rounded-xl border border-muted-foreground/20 max-w-sm animate-in fade-in slide-in-from-left-2"
                  style={{
                    animationDelay: `${index * 200}ms`,
                    animationDuration: '300ms',
                    animationFillMode: 'both'
                  }}
                >
                  {/* Horizontal connecting line to bubble */}
                  <div className="absolute left-[-12px] top-1/2 transform -translate-y-1/2 w-3 h-0.5 bg-muted-foreground/40"></div>
                  {/* Connection dot */}
                  <div className="absolute left-[-13px] top-1/2 transform -translate-y-1/2 w-1.5 h-1.5 bg-muted-foreground/60 rounded-full"></div>
                  {thought}
                </div>
              ))}

              {/* Active thinking indicator */}
              {message.isThinking && (
                <div
                  className="relative text-xs text-muted-foreground italic bg-muted/50 px-3 py-2 rounded-xl border border-muted-foreground/20 flex items-center gap-2 animate-in fade-in slide-in-from-left-2"
                  style={{
                    animationDelay: `${message.thinking.length * 200}ms`,
                    animationDuration: '300ms',
                    animationFillMode: 'both'
                  }}
                >
                  {/* Horizontal connecting line to bubble */}
                  <div className="absolute left-[-12px] top-1/2 transform -translate-y-1/2 w-3 h-0.5 bg-muted-foreground/40"></div>
                  {/* Connection dot */}
                  <div className="absolute left-[-13px] top-1/2 transform -translate-y-1/2 w-1.5 h-1.5 bg-muted-foreground/60 rounded-full"></div>
                  <div className="flex space-x-1">
                    <div className="w-1.5 h-1.5 bg-current rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                    <div className="w-1.5 h-1.5 bg-current rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                    <div className="w-1.5 h-1.5 bg-current rounded-full animate-bounce"></div>
                  </div>
                  <span>thinking...</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};