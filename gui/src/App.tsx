import { Routes, Route } from 'react-router-dom';
import { ThemeProvider } from "@/components/theme-provider"

import Layout from "@/layout/layout";
import Page from "@/app/page"
import WorkflowsPage from "@/app/workflows/workflows"
import WorkflowGraphPage from "@/app/workflow-graph/workflow-graph";

function App() {
  return (
    <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Page />} />
          <Route path="workflows" element={<WorkflowsPage />} />
          <Route path="workflow-graph" element={<WorkflowGraphPage />} />
        </Route>
      </Routes>
    </ThemeProvider>
  )
}

export default App
