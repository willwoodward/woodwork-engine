import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const iconBadgeVariants = cva(
  "flex items-center justify-center rounded-lg border",
  {
    variants: {
      variant: {
        default: "border-border bg-background text-foreground",
        // Priority variants with proper dark mode support
        priority_low: "border-green-200 bg-green-50 text-green-600 dark:border-green-800 dark:bg-green-950 dark:text-green-400",
        priority_medium: "border-yellow-200 bg-yellow-50 text-yellow-600 dark:border-yellow-800 dark:bg-yellow-950 dark:text-yellow-400",
        priority_high: "border-orange-200 bg-orange-50 text-orange-600 dark:border-orange-800 dark:bg-orange-950 dark:text-orange-400",
        priority_urgent: "border-red-200 bg-red-50 text-red-600 dark:border-red-800 dark:bg-red-950 dark:text-red-400",
      },
      size: {
        default: "p-2",
        sm: "p-1.5",
        lg: "p-3",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface IconBadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof iconBadgeVariants> {
  icon: React.ComponentType<{ className?: string }>;
}

function IconBadge({ className, variant, size, icon: Icon, ...props }: IconBadgeProps) {
  return (
    <div className={cn(iconBadgeVariants({ variant, size }), className)} {...props}>
      <Icon className="w-4 h-4" />
    </div>
  );
}

export { IconBadge, iconBadgeVariants };