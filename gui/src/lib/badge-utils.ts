import { type MockHumanInputRequest } from "@/data/mock-data";

// Type-safe variant getters for badges
export function getPriorityVariant(priority: MockHumanInputRequest['priority']) {
  return `priority_${priority}` as const;
}

export function getStatusVariant(status: MockHumanInputRequest['status']) {
  return `status_${status}` as const;
}

// Helper functions for getting display text
export function formatPriority(priority: MockHumanInputRequest['priority']): string {
  return priority.charAt(0).toUpperCase() + priority.slice(1);
}

export function formatStatus(status: MockHumanInputRequest['status']): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

// Get appropriate icon color classes for priorities (for use outside of badges)
export function getPriorityIconClass(priority: MockHumanInputRequest['priority']): string {
  switch (priority) {
    case 'low':
      return 'text-green-600 dark:text-green-400';
    case 'medium':
      return 'text-yellow-600 dark:text-yellow-400';
    case 'high':
      return 'text-orange-600 dark:text-orange-400';
    case 'urgent':
      return 'text-red-600 dark:text-red-400';
    default:
      return 'text-muted-foreground';
  }
}

// Get appropriate text color for status
export function getStatusTextClass(status: MockHumanInputRequest['status']): string {
  switch (status) {
    case 'pending':
      return 'text-yellow-600 dark:text-yellow-400';
    case 'approved':
      return 'text-green-600 dark:text-green-400';
    case 'rejected':
      return 'text-red-600 dark:text-red-400';
    case 'completed':
      return 'text-blue-600 dark:text-blue-400';
    default:
      return 'text-muted-foreground';
  }
}