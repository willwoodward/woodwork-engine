import { Routes, Route, Navigate, useParams } from 'react-router-dom';
import { ThemeProvider } from "@/components/theme-provider"

import Layout from "@/layout/layout";
import Page from "@/app/page"
import WorkflowsPage from "@/app/workflows/workflows"
import WorkflowGraphPage from "@/app/workflow-graph/workflow-graph";
import InboxPage from "@/app/inbox/page";
import { WorkflowBrowser } from "@/components/workflows/workflow-browser";
import TasksPage from "@/app/personal/tasks/page";
import MetricsPage from "@/app/personal/metrics/page";
import InsightsPage from "@/app/personal/insights/page";
import EventPipelinePage from "@/app/event-pipeline/page";

// Redirect component for workflow detail to workflows page with deeplink
function WorkflowDetailRedirect() {
  const { workflowId } = useParams<{ workflowId: string }>();
  return <Navigate to={`/workflows#workflow=${workflowId}`} replace />;
}

function App() {
  return (
    <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Page />} />
          <Route path="workflows" element={<WorkflowsPage />} />
          <Route path="workflows/:workflowId" element={<WorkflowDetailRedirect />} />
          <Route path="workflow-graph" element={<WorkflowGraphPage />} />
          <Route path="workflow-browser" element={<WorkflowBrowser />} />
          <Route path="inbox" element={<InboxPage />} />
          <Route path="personal/tasks" element={<TasksPage />} />
          <Route path="personal/metrics" element={<MetricsPage />} />
          <Route path="personal/insights" element={<InsightsPage />} />
          <Route path="event-pipeline" element={<EventPipelinePage />} />
        </Route>
      </Routes>
    </ThemeProvider>
  )
}

export default App
