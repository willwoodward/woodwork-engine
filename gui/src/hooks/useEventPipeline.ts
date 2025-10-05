import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

export interface EventListener {
  function: string;
  module: string;
}

export interface EventPipelineData {
  hooks: Record<string, EventListener[]>;
  pipes: Record<string, EventListener[]>;
  event_types: string[];
}

export function useEventPipeline() {
  return useQuery<EventPipelineData, Error>({
    queryKey: ["event-pipeline"],
    queryFn: async (): Promise<EventPipelineData> => {
      const response = await api.agent.get<EventPipelineData>('/api/event-pipeline');
      return response.data;
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 1,
  });
}
