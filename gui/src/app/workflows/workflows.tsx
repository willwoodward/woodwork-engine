import WorkflowsList from "@/app/workflows/workflows-list"

export default function WorkflowsPage() {
  return (
    <>
        <div className="flex h-full p-4 pt-0 gap-4">
            <div className="w-64 h-full bg-muted/50 rounded-xl p-4">
                <WorkflowsList />
            </div>
            <div className="flex-1 h-full bg-muted/50 rounded-xl" />
        </div>
    </>
  )
}
