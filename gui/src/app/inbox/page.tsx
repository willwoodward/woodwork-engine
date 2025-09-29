import { useState, useMemo } from "react";
import { Search, Filter, MoreHorizontal, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/ui";
import { RequestListItem } from "@/components/inbox/request-list-item";
import { RequestDetailView } from "@/components/inbox/request-detail-view";

import { useInboxRequests, useInboxResponse } from "@/hooks/useEnhancedAPI";
import { type HumanInputRequest } from "@/types/api-types";

// Convert between API types and component types
function convertToMockRequest(apiRequest: HumanInputRequest) {
  return {
    id: apiRequest.request_id,
    type: apiRequest.type,
    title: apiRequest.title,
    description: apiRequest.description,
    agentName: apiRequest.agent_name,
    workflowName: apiRequest.workflow_name,
    status: 'pending' as const, // API requests are always pending in inbox
    priority: apiRequest.priority,
    timestamp: new Date(apiRequest.created_at),
    content: apiRequest.metadata?.content,
    originalContent: apiRequest.metadata?.content,
    metadata: apiRequest.metadata,
    // Cross-session context
    sessionId: apiRequest.session_id,
    apiInputId: apiRequest.api_input_id
  };
}

export default function InboxPage() {
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Use the new API hooks
  const { requests: apiRequests, isLoading, error } = useInboxRequests();
  const inboxResponse = useInboxResponse();

  // Convert API requests to component format
  const requests = useMemo(() => {
    return apiRequests.map(convertToMockRequest);
  }, [apiRequests]);

  // Filter and search requests
  const filteredRequests = useMemo(() => {
    return requests.filter(request => {
      const matchesSearch = request.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                           request.agentName.toLowerCase().includes(searchQuery.toLowerCase()) ||
                           request.description.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesStatus = statusFilter === "all" || request.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [requests, searchQuery, statusFilter]);

  // Sort by priority and timestamp
  const sortedRequests = useMemo(() => {
    const priorityOrder = { urgent: 4, high: 3, medium: 2, low: 1 };
    return [...filteredRequests].sort((a, b) => {
      // First by status (pending first)
      if (a.status === 'pending' && b.status !== 'pending') return -1;
      if (a.status !== 'pending' && b.status === 'pending') return 1;

      // Then by priority
      const priorityDiff = priorityOrder[b.priority] - priorityOrder[a.priority];
      if (priorityDiff !== 0) return priorityDiff;

      // Finally by timestamp (newest first)
      return b.timestamp.getTime() - a.timestamp.getTime();
    });
  }, [filteredRequests]);

  const selectedRequest = selectedRequestId
    ? requests.find(r => r.id === selectedRequestId)
    : null;

  const pendingCount = requests.filter(r => r.status === 'pending').length;
  const totalCount = requests.length;

  const handleApprove = async (id: string) => {
    try {
      await inboxResponse.mutateAsync({
        request_id: id,
        action: 'approved',
        user_id: 'current_user', // TODO: Get from auth context
        responded_at: new Date().toISOString()
      });
    } catch (error) {
      console.error('Failed to approve request:', error);
    }
  };

  const handleReject = async (id: string) => {
    try {
      await inboxResponse.mutateAsync({
        request_id: id,
        action: 'rejected',
        user_id: 'current_user',
        responded_at: new Date().toISOString()
      });
    } catch (error) {
      console.error('Failed to reject request:', error);
    }
  };

  const handleUpdateContent = async (id: string, content: string) => {
    try {
      await inboxResponse.mutateAsync({
        request_id: id,
        action: 'edited',
        data: content,
        user_id: 'current_user',
        responded_at: new Date().toISOString()
      });
    } catch (error) {
      console.error('Failed to update content:', error);
    }
  };

  const handleSelectChoice = async (id: string, choice: string) => {
    try {
      await inboxResponse.mutateAsync({
        request_id: id,
        action: 'selected',
        data: choice,
        user_id: 'current_user',
        responded_at: new Date().toISOString()
      });
    } catch (error) {
      console.error('Failed to select choice:', error);
    }
  };

  const handleRespondToQuestion = async (id: string, response: string) => {
    try {
      await inboxResponse.mutateAsync({
        request_id: id,
        action: 'responded',
        data: response,
        user_id: 'current_user',
        responded_at: new Date().toISOString()
      });
    } catch (error) {
      console.error('Failed to respond to question:', error);
    }
  };

  return (
    <div className="flex h-full">
      {/* Left Panel - Request List */}
      <div className="w-80 border-r bg-muted/30 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b bg-card">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h1 className="text-lg font-semibold">Agent Requests</h1>
              <p className="text-sm text-muted-foreground">
                {pendingCount} pending • {totalCount} total
              </p>
            </div>
            <div className="flex gap-1">
              <Button variant="ghost" size="sm">
                <RefreshCw className="w-4 h-4" />
              </Button>
              <Button variant="ghost" size="sm">
                <MoreHorizontal className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Search */}
          <div className="relative mb-3">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search requests..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* Filters */}
          <div className="flex gap-2">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="flex-1 px-3 py-2 text-sm border border-border rounded-md bg-background"
            >
              <option value="all">All Status</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="completed">Completed</option>
            </select>
            <Button variant="outline" size="sm">
              <Filter className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Request List */}
        <div className="flex-1 overflow-auto">
          {isLoading ? (
            <div className="p-4 text-center">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">Loading requests...</p>
            </div>
          ) : error ? (
            <div className="p-4">
              <EmptyState message="Failed to load requests. Please try again." />
            </div>
          ) : sortedRequests.length === 0 ? (
            <div className="p-4">
              <EmptyState message={
                searchQuery || statusFilter !== "all"
                  ? "No requests match your filters"
                  : "No agent requests at this time"
              } />
            </div>
          ) : (
            sortedRequests.map((request) => (
              <RequestListItem
                key={request.id}
                request={request}
                isSelected={selectedRequestId === request.id}
                onClick={() => setSelectedRequestId(request.id)}
              />
            ))
          )}
        </div>
      </div>

      {/* Right Panel - Request Detail */}
      <div className="flex-1 bg-background">
        {selectedRequest ? (
          <RequestDetailView
            request={selectedRequest}
            onApprove={handleApprove}
            onReject={handleReject}
            onUpdateContent={handleUpdateContent}
            onSelectChoice={handleSelectChoice}
            onRespondToQuestion={handleRespondToQuestion}
          />
        ) : (
          <div className="h-full flex items-center justify-center">
            <EmptyState message="Select a request to view details" />
          </div>
        )}
      </div>
    </div>
  );
}