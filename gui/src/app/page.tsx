import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import {
  ArrowUp,
  Plus,
} from "lucide-react"

type InputResponse = {
  response: string;
};

export default function Page() {
  //   const { data, isLoading, error } = useQuery<InputResponse>({
  //   queryKey: ["workflows"],
  //   queryFn: async () => {
  //     const res = await fetch("/api/workflows/get");
  //     if (!res.ok) throw new Error("Failed to fetch workflows");
  //     return res.json();
  //   },
  // });

  // if (isLoading) return <p>Loading workflows...</p>;
  // if (error) return <p>Error loading workflows.</p>;
  // if (!data) return <p>No workflows found.</p>;

  const data: InputResponse = {
    response: "hey there"
  }

  return (
    <>
      <div className="flex flex-1 flex-col gap-4 p-4 pt-0">
        <div className="bg-muted/50 min-h-[100vh] flex-1 rounded-xl md:min-h-min px-64">
          <div className="flex flex-1 flex-col h-full" id="chat-box">
            <div className="flex-1 px-24 py-8">
              <p>{data.response}</p>
            </div>
            <div className="h-32 px-8 py-8 flex bg-muted/50 rounded-3xl mb-4">
              <div className="w-16 py-3">
                <Button>
                  <Plus />
                </Button>
              </div>
              <div className="flex-1">
                <Textarea />
              </div>
              <div className="w-16 ml-4 py-3">
                <Button>
                  <ArrowUp />
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
      {/* <div className="flex flex-1 flex-col gap-4 p-4 pt-0">
        <div className="grid auto-rows-min gap-4 md:grid-cols-3">
          <div className="bg-muted/50 aspect-video rounded-xl" />
          <div className="bg-muted/50 aspect-video rounded-xl" />
          <div className="bg-muted/50 aspect-video rounded-xl" />
        </div>
        <div className="bg-muted/50 min-h-[100vh] flex-1 rounded-xl md:min-h-min" />
      </div> */}
    </>
  )
}
