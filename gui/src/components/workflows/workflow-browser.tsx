import { useState } from 'react';
import { Play, Search, Bot, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui';

import { useWorkflows, useAgents, useTriggerWorkflow } from '@/hooks/useEnhancedAPI';
import type { Workflow, Agent } from '@/types/api-types';

interface WorkflowCardProps {
  workflow: Workflow;
  availableAgents: Agent[];
  onTrigger: (inputs: any, targetAgent?: string) => void;
  isTriggering?: boolean;
}

function WorkflowCard({ workflow, availableAgents, onTrigger, isTriggering }: WorkflowCardProps) {
  const [selectedAgent, setSelectedAgent] = useState<string>('');
  const [inputs, setInputs] = useState<Record<string, string>>({});

  const handleTrigger = () => {
    const processedInputs = Object.entries(inputs).reduce((acc, [key, value]) => {
      // Try to parse JSON values, fallback to string
      try {
        acc[key] = JSON.parse(value);
      } catch {
        acc[key] = value;
      }
      return acc;
    }, {} as Record<string, any>);

    onTrigger(processedInputs, selectedAgent || undefined);
  };

  const compatibleAgents = availableAgents.filter(agent =>
    !workflow.requiredCapabilities ||
    workflow.requiredCapabilities.every(cap => agent.capabilities.includes(cap))
  );

  return (
    <Card className="workflow-card">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">{workflow.name}</CardTitle>
          <div className="flex items-center gap-2">
            {workflow.category && (
              <Badge variant="outline">{workflow.category}</Badge>
            )}
            {workflow.status && (
              <Badge variant={workflow.status === 'active' ? 'default' : 'secondary'}>
                {workflow.status}
              </Badge>
            )}
          </div>
        </div>
        {workflow.description && (
          <CardDescription>{workflow.description}</CardDescription>
        )}
      </CardHeader>

      <CardContent>
        <div className="space-y-4">
          {/* Required Capabilities */}
          {workflow.requiredCapabilities && workflow.requiredCapabilities.length > 0 && (
            <div>
              <p className="text-sm font-medium mb-2">Required Capabilities:</p>
              <div className="flex flex-wrap gap-1">
                {workflow.requiredCapabilities.map(cap => (
                  <Badge key={cap} variant="secondary" className="text-xs">
                    {cap}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Agent Selection */}
          {compatibleAgents.length > 0 && (
            <div>
              <label className="text-sm font-medium">Target Agent (optional):</label>
              <select
                value={selectedAgent}
                onChange={(e) => setSelectedAgent(e.target.value)}
                className="w-full mt-1 px-3 py-2 text-sm border border-border rounded-md bg-background"
              >
                <option value="">Auto-select best agent</option>
                {compatibleAgents.map(agent => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name} ({agent.status})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Simple Input Fields (for MVP) */}
          <div>
            <label className="text-sm font-medium">Workflow Inputs (JSON):</label>
            <textarea
              placeholder='{"key": "value", "param": 123}'
              value={inputs['json'] || ''}
              onChange={(e) => setInputs({ json: e.target.value })}
              className="w-full mt-1 px-3 py-2 text-sm border border-border rounded-md bg-background min-h-[80px]"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Enter workflow inputs as JSON object
            </p>
          </div>

          {/* Trigger Button */}
          <Button
            onClick={handleTrigger}
            disabled={isTriggering || compatibleAgents.length === 0}
            className="w-full"
          >
            {isTriggering ? (
              <>
                <Clock className="w-4 h-4 mr-2 animate-spin" />
                Triggering...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                Trigger Workflow
              </>
            )}
          </Button>

          {compatibleAgents.length === 0 && (
            <p className="text-xs text-muted-foreground text-center">
              No compatible agents available
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function WorkflowBrowser() {
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');

  const { data: workflowData, isLoading: workflowsLoading, error: workflowsError } = useWorkflows({
    search: searchTerm,
    category: categoryFilter,
    limit: 50
  });

  const { data: agentData, isLoading: agentsLoading } = useAgents();
  const triggerWorkflow = useTriggerWorkflow();

  const workflows = workflowData?.workflows || [];
  const agents = agentData?.agents || [];
  const categories = workflowData?.categories || [];

  const handleTriggerWorkflow = async (workflow: Workflow, inputs: any, targetAgent?: string) => {
    try {
      // Parse JSON inputs if provided as string
      let processedInputs = inputs;
      if (inputs.json && typeof inputs.json === 'string') {
        try {
          processedInputs = JSON.parse(inputs.json);
        } catch (e) {
          console.error('Invalid JSON inputs:', e);
          return;
        }
      }

      await triggerWorkflow.mutateAsync({
        workflowId: workflow.id,
        inputs: processedInputs,
        targetAgent,
        priority: 'medium'
      });
    } catch (error) {
      console.error('Failed to trigger workflow:', error);
    }
  };

  if (workflowsLoading || agentsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Clock className="w-8 h-8 animate-spin mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">Loading workflows and agents...</p>
        </div>
      </div>
    );
  }

  if (workflowsError) {
    return (
      <div className="flex items-center justify-center h-64">
        <EmptyState message="Failed to load workflows. Please try again." />
      </div>
    );
  }

  return (
    <div className="workflow-browser p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-2">Workflow Browser</h1>
        <p className="text-muted-foreground">
          Trigger workflows on available agents across your system
        </p>
      </div>

      {/* Filters */}
      <div className="flex gap-4 mb-6">
        <div className="flex-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search workflows..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        {categories.length > 0 && (
          <div className="w-48">
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-border rounded-md bg-background"
            >
              <option value="">All Categories</option>
              {categories.map(category => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Agent Status */}
      <div className="mb-6 p-4 bg-muted/30 rounded-lg">
        <div className="flex items-center gap-2 mb-2">
          <Bot className="w-4 h-4" />
          <span className="font-medium">Available Agents: {agents.length}</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {agents.map(agent => (
            <Badge
              key={agent.id}
              variant={agent.status === 'online' ? 'default' : 'secondary'}
            >
              {agent.name} ({agent.status})
            </Badge>
          ))}
        </div>
      </div>

      {/* Workflow Grid */}
      {workflows.length === 0 ? (
        <EmptyState
          message={
            searchTerm || categoryFilter
              ? "No workflows match your filters"
              : "No workflows available"
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {workflows.map(workflow => (
            <WorkflowCard
              key={workflow.id}
              workflow={workflow}
              availableAgents={agents}
              onTrigger={(inputs, targetAgent) =>
                handleTriggerWorkflow(workflow, inputs, targetAgent)
              }
              isTriggering={triggerWorkflow.isPending}
            />
          ))}
        </div>
      )}
    </div>
  );
}