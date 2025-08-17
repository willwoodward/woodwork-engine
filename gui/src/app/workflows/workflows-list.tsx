import { useQuery } from "@tanstack/react-query";

type WorkflowSummary = {
  id: string;
  name: string;
};

export default function WorkflowsList() {
  const { data, isLoading, error } = useQuery<WorkflowSummary[]>({
    queryKey: ["workflows"],
    queryFn: async () => {
      const res = await fetch("/api/workflows/get");
      if (!res.ok) throw new Error("Failed to fetch workflows");
      return res.json();
    },
  });

  if (isLoading) return <p>Loading workflows...</p>;
  if (error) return <p>Error loading workflows.</p>;
  if (!data || data.length === 0) return <p>No workflows found.</p>;

  return (
    <ul className="space-y-2 overflow-auto max-h-full">
      {data.map((workflow) => (
        <li key={workflow.id} className="cursor-pointer rounded-md p-2 hover:bg-accent">
          {workflow.name}
        </li>
      ))}
    </ul>
  );
}
