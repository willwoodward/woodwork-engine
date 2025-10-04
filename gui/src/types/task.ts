export type TaskPriority = 'low' | 'medium' | 'high';

export type TaskTag = 'work' | 'personal' | 'admin' | string;

export interface Task {
  id: string;
  title: string;
  tags: TaskTag[];
  estimatedTime?: number; // in minutes
  priority: TaskPriority;
  dateCreated: Date;
  dateCompleted?: Date;
  actualTime?: number; // in minutes
  effortRating?: number; // 1-5 scale
  workflowUsed?: string;
  notes?: string;
  completed: boolean;
}

export interface TaskMetrics {
  timeSaved: number; // in minutes
  completionRate: number; // 0-100
  repetitionReduction: number; // 0-100
  workflowAdoptionRate: number; // 0-100
}

export interface Suggestion {
  id: string;
  type: 'workflow' | 'optimization' | 'batching';
  title: string;
  description: string;
  relatedTasks?: string[];
  dateCreated: Date;
  accepted?: boolean;
}

export interface Insight {
  id: string;
  type: 'repetition' | 'bottleneck' | 'optimization';
  title: string;
  description: string;
  relatedTasks?: string[];
  dateCreated: Date;
}
