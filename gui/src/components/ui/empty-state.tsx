

interface EmptyStateProps {
  message: string;
  className?: string;
}

export const EmptyState = ({ message, className = "" }: EmptyStateProps) => (
  <div className={`text-sm text-muted-foreground p-4 text-center border rounded-lg border-dashed ${className}`}>
    {message}
  </div>
);