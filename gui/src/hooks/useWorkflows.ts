import { useQuery } from '@tanstack/react-query';

export type WorkflowStep = {
  id: string;
  name?: string;
  tool?: string;
  input?: Record<string, unknown> | null;
};

export type Workflow = {
  id: string;
  name?: string;
  steps?: WorkflowStep[];
};

async function fetchWorkflows(): Promise<Workflow[]> {
  try {
    const res = await fetch('/api/workflows');
    if (!res.ok) {
      // If the endpoint doesn't exist yet, return empty list instead of throwing.
      return [];
    }
    const data = await res.json();
    // Expecting data to be an array of workflows; if it's wrapped, try to be permissive.
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.workflows)) return data.workflows;
    return [];
  } catch (err) {
    // On network error, return empty list and let react-query manage retries
    return [];
  }
}

export function useWorkflows() {
  return useQuery({
    queryKey: ['workflows'],
    queryFn: fetchWorkflows,
    // Poll frequently so the UI updates automatically when new workflows are created.
    refetchInterval: 2000,
    // Keep previous data to avoid UI flicker
    keepPreviousData: true,
  });
}
