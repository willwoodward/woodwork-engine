import { useState, useMemo } from "react";
import { useTasks } from "@/hooks/useTasks";
import { useTaskInsights } from "@/hooks/useTaskInsights";
import { useTaskSuggestions } from "@/hooks/useTaskSuggestions";
import { InsightCard } from "@/components/tasks/insight-card";
import { SuggestionCard } from "@/components/tasks/suggestion-card";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { Sparkles, TrendingUp, AlertCircle, Lightbulb, Filter } from "lucide-react";
import { Separator } from "@/components/ui/separator";

type ViewType = "all" | "insights" | "suggestions";
type InsightFilterType = "all" | "repetition" | "bottleneck" | "optimization";
type SuggestionFilterType = "all" | "pending" | "accepted";

export default function InsightsPage() {
  const { tasks } = useTasks();
  const insights = useTaskInsights(tasks);
  const { suggestions } = useTaskSuggestions();

  const [view, setView] = useState<ViewType>("all");
  const [insightFilter, setInsightFilter] = useState<InsightFilterType>("all");
  const [suggestionFilter, setSuggestionFilter] = useState<SuggestionFilterType>("pending");

  // Filter insights
  const filteredInsights = useMemo(() => {
    if (insightFilter === "all") return insights;
    return insights.filter((i) => i.type === insightFilter);
  }, [insights, insightFilter]);

  // Filter suggestions
  const filteredSuggestions = useMemo(() => {
    if (suggestionFilter === "all") return suggestions;
    if (suggestionFilter === "pending") return suggestions.filter((s) => !s.accepted);
    return suggestions.filter((s) => s.accepted);
  }, [suggestions, suggestionFilter]);

  // Counts
  const totalInsights = insights.length;
  const totalSuggestions = suggestions.length;
  const pendingSuggestions = suggestions.filter((s) => !s.accepted).length;

  const handleAcceptSuggestion = (id: string) => {
    console.log("Accept suggestion:", id);
    // TODO: Implement with API
  };

  const handleRejectSuggestion = (id: string) => {
    console.log("Reject suggestion:", id);
    // TODO: Implement with API
  };

  const showInsights = view === "all" || view === "insights";
  const showSuggestions = view === "all" || view === "suggestions";

  return (
    <div className="flex h-full p-4 pt-0 gap-4">
      {/* Left Panel - Filters & Stats */}
      <div className="w-64 h-full bg-muted/50 rounded-xl p-4 space-y-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="h-5 w-5 text-purple-500" />
            <h2 className="text-lg font-semibold">Intelligence</h2>
          </div>
          <p className="text-xs text-muted-foreground">
            Insights & workflow suggestions
          </p>
        </div>

        <Separator />

        {/* View Toggle */}
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground mb-2">VIEW</p>
          <Button
            variant={view === "all" ? "default" : "ghost"}
            className="w-full justify-start"
            onClick={() => setView("all")}
          >
            <Filter className="h-4 w-4 mr-2" />
            All ({totalInsights + totalSuggestions})
          </Button>
          <Button
            variant={view === "insights" ? "default" : "ghost"}
            className="w-full justify-start"
            onClick={() => setView("insights")}
          >
            <Sparkles className="h-4 w-4 mr-2" />
            Insights ({totalInsights})
          </Button>
          <Button
            variant={view === "suggestions" ? "default" : "ghost"}
            className="w-full justify-start"
            onClick={() => setView("suggestions")}
          >
            <Lightbulb className="h-4 w-4 mr-2" />
            Suggestions ({pendingSuggestions})
          </Button>
        </div>

        <Separator />

        {/* Quick Stats */}
        <div className="space-y-3">
          <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/20">
            <p className="text-xs font-medium text-purple-500 mb-1">Insights</p>
            <p className="text-2xl font-bold">{totalInsights}</p>
            <p className="text-xs text-muted-foreground mt-1">patterns found</p>
          </div>
          <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
            <p className="text-xs font-medium text-yellow-500 mb-1">Suggestions</p>
            <p className="text-2xl font-bold">{pendingSuggestions}</p>
            <p className="text-xs text-muted-foreground mt-1">pending action</p>
          </div>
        </div>
      </div>

      {/* Right Panel - Content */}
      <div className="flex-1 h-full bg-muted/50 rounded-xl overflow-auto">
        <div className="p-6">
          <div className="max-w-4xl mx-auto space-y-6">
            {/* Suggestions Section */}
            {showSuggestions && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-2xl font-bold">Workflow Suggestions</h2>
                    <p className="text-sm text-muted-foreground mt-1">
                      AI-powered recommendations to optimize your workflow
                    </p>
                  </div>
                  {view === "suggestions" && (
                    <div className="flex gap-2">
                      <Button
                        variant={suggestionFilter === "pending" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setSuggestionFilter("pending")}
                      >
                        Pending
                      </Button>
                      <Button
                        variant={suggestionFilter === "accepted" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setSuggestionFilter("accepted")}
                      >
                        Accepted
                      </Button>
                      <Button
                        variant={suggestionFilter === "all" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setSuggestionFilter("all")}
                      >
                        All
                      </Button>
                    </div>
                  )}
                </div>

                {filteredSuggestions.length === 0 ? (
                  <EmptyState
                    icon={Lightbulb}
                    title="No suggestions"
                    description="Complete tasks to get workflow recommendations"
                  />
                ) : (
                  <div className="grid gap-4">
                    {filteredSuggestions.map((suggestion) => (
                      <SuggestionCard
                        key={suggestion.id}
                        suggestion={suggestion}
                        onAccept={handleAcceptSuggestion}
                        onReject={handleRejectSuggestion}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Separator if showing both */}
            {showInsights && showSuggestions && filteredSuggestions.length > 0 && (
              <Separator className="my-8" />
            )}

            {/* Insights Section */}
            {showInsights && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-2xl font-bold">Pattern Insights</h2>
                    <p className="text-sm text-muted-foreground mt-1">
                      Patterns detected from your task history
                    </p>
                  </div>
                  {view === "insights" && (
                    <div className="flex gap-2">
                      <Button
                        variant={insightFilter === "all" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setInsightFilter("all")}
                      >
                        All
                      </Button>
                      <Button
                        variant={insightFilter === "repetition" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setInsightFilter("repetition")}
                      >
                        Patterns
                      </Button>
                      <Button
                        variant={insightFilter === "bottleneck" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setInsightFilter("bottleneck")}
                      >
                        Bottlenecks
                      </Button>
                      <Button
                        variant={insightFilter === "optimization" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setInsightFilter("optimization")}
                      >
                        Optimizations
                      </Button>
                    </div>
                  )}
                </div>

                {filteredInsights.length === 0 ? (
                  <EmptyState
                    icon={Sparkles}
                    title="No insights yet"
                    description="Complete more tasks to discover patterns"
                  />
                ) : (
                  <div className="grid gap-4">
                    {filteredInsights.map((insight) => (
                      <InsightCard
                        key={insight.id}
                        type={insight.type}
                        title={insight.title}
                        description={insight.description}
                        taskCount={insight.relatedTasks?.length}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Empty state when both are empty */}
            {filteredInsights.length === 0 && filteredSuggestions.length === 0 && (
              <EmptyState
                icon={Sparkles}
                title="No insights or suggestions yet"
                description="Complete tasks to get personalized insights and workflow recommendations"
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
