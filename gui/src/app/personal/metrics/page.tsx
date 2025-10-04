import { useTasks } from "@/hooks/useTasks";
import { useTaskMetrics } from "@/hooks/useTaskMetrics";
import { MetricCard } from "@/components/tasks/metric-card";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Clock,
  CheckCircle,
  TrendingDown,
  Workflow,
  BarChart3,
  TrendingUp,
  Calendar,
  Target,
} from "lucide-react";
import { Separator } from "@/components/ui/separator";

export default function MetricsPage() {
  const { tasks } = useTasks();
  const metrics = useTaskMetrics(tasks);

  const completedTasks = tasks.filter((t) => t.completed);
  const hasData = completedTasks.length > 0;

  // Calculate additional stats
  const activeTasks = tasks.filter((t) => !t.completed);
  const highPriorityTasks = activeTasks.filter((t) => t.priority === "high");
  const tasksCompletedToday = completedTasks.filter((t) => {
    if (!t.dateCompleted) return false;
    const today = new Date();
    return (
      t.dateCompleted.getDate() === today.getDate() &&
      t.dateCompleted.getMonth() === today.getMonth() &&
      t.dateCompleted.getFullYear() === today.getFullYear()
    );
  });

  return (
    <div className="flex h-full p-4 pt-0 gap-4">
      {/* Left Panel - Quick Stats */}
      <div className="w-64 h-full bg-muted/50 rounded-xl p-4 space-y-4">
        <div>
          <h2 className="text-lg font-semibold mb-1">Overview</h2>
          <p className="text-xs text-muted-foreground">
            Your productivity at a glance
          </p>
        </div>

        <Separator />

        <div className="space-y-3">
          <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20">
            <div className="flex items-center gap-2 mb-1">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <p className="text-xs font-medium text-green-500">Completed</p>
            </div>
            <p className="text-2xl font-bold">{completedTasks.length}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {metrics.completionRate}% complete
            </p>
          </div>

          <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
            <div className="flex items-center gap-2 mb-1">
              <Target className="h-4 w-4 text-blue-500" />
              <p className="text-xs font-medium text-blue-500">Active</p>
            </div>
            <p className="text-2xl font-bold">{activeTasks.length}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {highPriorityTasks.length} high priority
            </p>
          </div>

          <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/20">
            <div className="flex items-center gap-2 mb-1">
              <Calendar className="h-4 w-4 text-purple-500" />
              <p className="text-xs font-medium text-purple-500">Today</p>
            </div>
            <p className="text-2xl font-bold">{tasksCompletedToday.length}</p>
            <p className="text-xs text-muted-foreground mt-1">completed</p>
          </div>

          <div className="p-3 rounded-lg bg-orange-500/10 border border-orange-500/20">
            <div className="flex items-center gap-2 mb-1">
              <Clock className="h-4 w-4 text-orange-500" />
              <p className="text-xs font-medium text-orange-500">Time Saved</p>
            </div>
            <p className="text-2xl font-bold">{Math.abs(metrics.timeSaved)}m</p>
            <p className="text-xs text-muted-foreground mt-1">
              {metrics.timeSaved >= 0 ? "saved" : "over"}
            </p>
          </div>
        </div>
      </div>

      {/* Right Panel - Detailed Metrics */}
      <div className="flex-1 h-full bg-muted/50 rounded-xl overflow-auto">
        <div className="p-6">
          <div className="max-w-6xl mx-auto space-y-6">
            {/* Header */}
            <div>
              <h1 className="text-3xl font-bold">Metrics Dashboard</h1>
              <p className="text-muted-foreground mt-1">
                Track your productivity and efficiency
              </p>
            </div>

            {!hasData ? (
              <EmptyState
                icon={BarChart3}
                title="No data yet"
                description="Complete some tasks to see your metrics"
              />
            ) : (
              <>
                {/* Key metrics */}
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                  <MetricCard
                    title="Time Saved"
                    value={`${Math.abs(metrics.timeSaved)}m`}
                    description={metrics.timeSaved >= 0 ? "Under estimated time" : "Over estimated time"}
                    icon={Clock}
                  />
                  <MetricCard
                    title="Completion Rate"
                    value={`${metrics.completionRate}%`}
                    description={`${completedTasks.length} of ${tasks.length} tasks`}
                    icon={CheckCircle}
                  />
                  <MetricCard
                    title="Repetition Reduction"
                    value={`${metrics.repetitionReduction}%`}
                    description="Unique vs repeated tasks"
                    icon={TrendingDown}
                  />
                  <MetricCard
                    title="Workflow Adoption"
                    value={`${metrics.workflowAdoptionRate}%`}
                    description="Tasks using workflows"
                    icon={Workflow}
                  />
                </div>

                <Separator />

                {/* Additional insights */}
                <div className="space-y-4">
                  <h2 className="text-xl font-semibold">Task Breakdown</h2>
                  <div className="grid gap-4 md:grid-cols-3">
                    <MetricCard
                      title="Total Tasks"
                      value={tasks.length}
                      icon={BarChart3}
                    />
                    <MetricCard
                      title="Active Tasks"
                      value={activeTasks.length}
                      icon={Clock}
                    />
                    <MetricCard
                      title="Completed Tasks"
                      value={completedTasks.length}
                      icon={CheckCircle}
                    />
                  </div>
                </div>

                {/* Effort analysis */}
                {completedTasks.some((t) => t.effortRating) && (
                  <>
                    <Separator />
                    <div className="space-y-4">
                      <h2 className="text-xl font-semibold">Effort Analysis</h2>
                      <div className="grid gap-4 md:grid-cols-3">
                        <MetricCard
                          title="Average Effort"
                          value={
                            Math.round(
                              (completedTasks
                                .filter((t) => t.effortRating)
                                .reduce((acc, t) => acc + (t.effortRating || 0), 0) /
                                completedTasks.filter((t) => t.effortRating).length) *
                                10
                            ) / 10
                          }
                          description="On a scale of 1-5"
                          icon={TrendingUp}
                        />
                        <MetricCard
                          title="High Effort Tasks"
                          value={
                            completedTasks.filter((t) => (t.effortRating || 0) >= 4)
                              .length
                          }
                          description="Effort rating 4-5"
                          icon={BarChart3}
                        />
                        <MetricCard
                          title="Low Effort Tasks"
                          value={
                            completedTasks.filter((t) => (t.effortRating || 0) <= 2)
                              .length
                          }
                          description="Effort rating 1-2"
                          icon={CheckCircle}
                        />
                      </div>
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
