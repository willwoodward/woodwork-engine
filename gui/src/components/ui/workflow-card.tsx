import React from "react";

interface WorkflowCardProps {
  id: string;
  name: string;
  stepCount: number;
  onClick?: () => void;
  className?: string;
}

export const WorkflowCard = ({ id, name, stepCount, onClick, className = "" }: WorkflowCardProps) => (
  <div
    className={`p-3 rounded-lg bg-card border hover:bg-accent transition-colors cursor-pointer ${className}`}
    onClick={onClick}
  >
    <div className="font-medium text-card-foreground">{name || id}</div>
    <div className="text-xs text-muted-foreground mt-1">
      {stepCount} step{stepCount !== 1 ? 's' : ''}
    </div>
  </div>
);