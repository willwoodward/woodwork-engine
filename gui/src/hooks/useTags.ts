import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { TaskTag } from "@/types/task";

const QUERY_KEY = ["tags"];
const API_URL = "http://localhost:8001/api/tags";

// Fallback tags when server is offline
const fallbackTags: TaskTag[] = ["work", "personal", "admin"];

export function useTags() {
  const queryClient = useQueryClient();

  const { data: tags = fallbackTags } = useQuery<TaskTag[]>({
    queryKey: QUERY_KEY,
    queryFn: async () => {
      const response = await fetch(API_URL);
      if (!response.ok) throw new Error("Failed to fetch tags");
      return response.json();
    },
    staleTime: 30000,
    retry: false,
    meta: {
      fallbackData: fallbackTags,
    },
  });

  const addTagMutation = useMutation({
    mutationFn: async (tag: string) => {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tag }),
      });
      if (!response.ok) throw new Error("Failed to add tag");
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });

  const removeTagMutation = useMutation({
    mutationFn: async (tag: string) => {
      const response = await fetch(`${API_URL}/${encodeURIComponent(tag)}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error("Failed to remove tag");
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });

  const addTag = (tag: string) => {
    const normalizedTag = tag.trim().toLowerCase();
    if (!normalizedTag || tags.includes(normalizedTag)) return;
    addTagMutation.mutate(normalizedTag);
  };

  const removeTag = (tag: string) => {
    removeTagMutation.mutate(tag);
  };

  return {
    tags,
    addTag,
    removeTag,
  };
}
