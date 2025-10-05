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
  ArrowUp,
  ArrowDown,
} from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import type { ChartConfig } from "@/components/ui/chart";
import { Bar, BarChart, CartesianGrid, XAxis, Line, LineChart } from "recharts";

export default function MetricsPage() {
  const { tasks } = useTasks();
  const metrics = useTaskMetrics(tasks);

  const completedTasks = tasks.filter((t) => t.completed);
  const hasData = completedTasks.length > 0;

  // Calculate additional stats
  const activeTasks = tasks.filter((t) => !t.completed);
  const highPriorityTasks = activeTasks.filter((t) => t.priority === "high");

  // Date filters
  const now = new Date();
  const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  const twoWeeksAgo = new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000);

  const tasksCompletedToday = completedTasks.filter((t) => {
    if (!t.dateCompleted) return false;
    const today = new Date();
    return (
      t.dateCompleted.getDate() === today.getDate() &&
      t.dateCompleted.getMonth() === today.getMonth() &&
      t.dateCompleted.getFullYear() === today.getFullYear()
    );
  });

  const tasksCompletedThisWeek = completedTasks.filter((t) =>
    t.dateCompleted && new Date(t.dateCompleted) >= weekAgo
  );

  const tasksCompletedLastWeek = completedTasks.filter((t) =>
    t.dateCompleted && new Date(t.dateCompleted) >= twoWeeksAgo && new Date(t.dateCompleted) < weekAgo
  );

  // Calculate week-over-week trends
  const thisWeekCount = tasksCompletedThisWeek.length;
  const lastWeekCount = tasksCompletedLastWeek.length;
  const completionTrend = lastWeekCount === 0 ? 100 : Math.round(((thisWeekCount - lastWeekCount) / lastWeekCount) * 100);

  // Calculate weekly time saved trend
  const thisWeekTimeSaved = tasksCompletedThisWeek.reduce((acc, t) =>
    acc + ((t.estimatedTime || 0) - (t.actualTime || 0)), 0
  );
  const lastWeekTimeSaved = tasksCompletedLastWeek.reduce((acc, t) =>
    acc + ((t.estimatedTime || 0) - (t.actualTime || 0)), 0
  );
  const timeSavedTrend = lastWeekTimeSaved === 0 ? 100 : Math.round(((thisWeekTimeSaved - lastWeekTimeSaved) / Math.abs(lastWeekTimeSaved)) * 100);

  // Workflow adoption trend
  const thisWeekWorkflowTasks = tasksCompletedThisWeek.filter(t => t.workflowUsed).length;
  const lastWeekWorkflowTasks = tasksCompletedLastWeek.filter(t => t.workflowUsed).length;
  const thisWeekWorkflowRate = thisWeekCount === 0 ? 0 : Math.round((thisWeekWorkflowTasks / thisWeekCount) * 100);
  const lastWeekWorkflowRate = lastWeekCount === 0 ? 0 : Math.round((lastWeekWorkflowTasks / lastWeekCount) * 100);
  const workflowTrend = lastWeekWorkflowRate === 0 ? 100 : Math.round(((thisWeekWorkflowRate - lastWeekWorkflowRate) / lastWeekWorkflowRate) * 100);

  // Chart data - last 7 days
  const last7Days = Array.from({ length: 7 }, (_, i) => {
    const date = new Date(now);
    date.setDate(date.getDate() - (6 - i));
    return date;
  });

  const dailyCompletionData = last7Days.map(date => {
    const dayTasks = completedTasks.filter(t => {
      if (!t.dateCompleted) return false;
      const completed = new Date(t.dateCompleted);
      return (
        completed.getDate() === date.getDate() &&
        completed.getMonth() === date.getMonth() &&
        completed.getFullYear() === date.getFullYear()
      );
    });

    return {
      date: date.toLocaleDateString('en-US', { weekday: 'short' }),
      completed: dayTasks.length,
      withWorkflow: dayTasks.filter(t => t.workflowUsed).length,
    };
  });

  const effortDistribution = [
    { rating: "1", count: completedTasks.filter(t => t.effortRating === 1).length },
    { rating: "2", count: completedTasks.filter(t => t.effortRating === 2).length },
    { rating: "3", count: completedTasks.filter(t => t.effortRating === 3).length },
    { rating: "4", count: completedTasks.filter(t => t.effortRating === 4).length },
    { rating: "5", count: completedTasks.filter(t => t.effortRating === 5).length },
  ];

  // Chart configurations
  const completionChartConfig = {
    completed: {
      label: "Completed",
      color: "hsl(0 0% 90%)",
    },
    withWorkflow: {
      label: "With Workflow",
      color: "hsl(0 0% 60%)",
    },
  } satisfies ChartConfig;

  const effortChartConfig = {
    count: {
      label: "Tasks",
      color: "hsl(0 0% 80%)",
    },
  } satisfies ChartConfig;

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
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-green-500" />
                <p className="text-xs font-medium text-green-500">This Week</p>
              </div>
              {completionTrend !== 0 && (
                <div className={`flex items-center gap-0.5 text-xs ${completionTrend > 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {completionTrend > 0 ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
                  {Math.abs(completionTrend)}%
                </div>
              )}
            </div>
            <p className="text-2xl font-bold">{thisWeekCount}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {lastWeekCount} last week
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
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-orange-500" />
                <p className="text-xs font-medium text-orange-500">Time Saved</p>
              </div>
              {timeSavedTrend !== 0 && (
                <div className={`flex items-center gap-0.5 text-xs ${timeSavedTrend > 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {timeSavedTrend > 0 ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
                  {Math.abs(timeSavedTrend)}%
                </div>
              )}
            </div>
            <p className="text-2xl font-bold">{Math.abs(thisWeekTimeSaved)}m</p>
            <p className="text-xs text-muted-foreground mt-1">
              this week
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

                {/* Charts */}
                <div className="grid gap-4 md:grid-cols-2">
                  {/* Daily Completion Chart */}
                  <Card>
                    <CardHeader>
                      <CardTitle>Daily Completions (Last 7 Days)</CardTitle>
                      <CardDescription>Track your daily task completion rate</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <ChartContainer config={completionChartConfig}>
                        <LineChart data={dailyCompletionData} width={500} height={300}>
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                          <XAxis
                            dataKey="date"
                            tickLine={false}
                            axisLine={false}
                            tickMargin={8}
                            className="text-muted-foreground"
                          />
                          <ChartTooltip content={<ChartTooltipContent />} />
                          <Line
                            dataKey="completed"
                            type="monotone"
                            stroke="var(--color-completed)"
                            strokeWidth={2}
                            dot={false}
                          />
                          <Line
                            dataKey="withWorkflow"
                            type="monotone"
                            stroke="var(--color-withWorkflow)"
                            strokeWidth={2}
                            dot={false}
                          />
                        </LineChart>
                      </ChartContainer>
                    </CardContent>
                  </Card>

                  {/* Effort Distribution Chart */}
                  {completedTasks.some((t) => t.effortRating) && (
                    <Card>
                      <CardHeader>
                        <CardTitle>Effort Distribution</CardTitle>
                        <CardDescription>Task difficulty breakdown (1-5 scale)</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <ChartContainer config={effortChartConfig}>
                          <BarChart data={effortDistribution} width={500} height={300}>
                            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                            <XAxis
                              dataKey="rating"
                              tickLine={false}
                              tickMargin={10}
                              axisLine={false}
                              className="text-muted-foreground"
                            />
                            <ChartTooltip content={<ChartTooltipContent />} />
                            <Bar
                              dataKey="count"
                              fill="var(--color-count)"
                              radius={[8, 8, 0, 0]}
                            />
                          </BarChart>
                        </ChartContainer>
                      </CardContent>
                    </Card>
                  )}
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
