import React from "react";

interface SidebarSectionProps {
  title: string;
  children: React.ReactNode;
  className?: string;
}

export const SidebarSection = ({ title, children, className = "" }: SidebarSectionProps) => (
  <div className={`p-3 rounded-lg bg-card border ${className}`}>
    <h5 className="font-medium text-card-foreground mb-2">{title}</h5>
    {children}
  </div>
);