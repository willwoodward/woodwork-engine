import { Routes, Route } from 'react-router-dom';
import { ThemeProvider } from "@/components/theme-provider"

import Layout from "@/layout/layout";
import Page from "@/app/dashboard/page"
import WorkflowsPage from "@/app/dashboard/workflows"

function App() {
  return (
    <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Page />} />
          <Route path="workflows" element={<WorkflowsPage />} />
        </Route>
      </Routes>
    </ThemeProvider>
  )
}

export default App
