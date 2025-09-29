import { useLocation } from "react-router-dom";
import { useMemo } from "react";

export interface BreadcrumbItem {
  label: string;
  href?: string;
  isCurrentPage?: boolean;
}

// Route configuration for breadcrumbs
const routeConfig: Record<string, BreadcrumbItem[]> = {
  "/": [
    { label: "Playground", href: "#" },
    { label: "Home", isCurrentPage: true }
  ],
  "/workflows": [
    { label: "Playground", href: "#" },
    { label: "Workflow Builder", isCurrentPage: true }
  ],
  "/workflow-graph": [
    { label: "Playground", href: "#" },
    { label: "Workflow View", isCurrentPage: true }
  ],
  "/inbox": [
    { label: "Playground", href: "#" },
    { label: "Agent Requests", isCurrentPage: true }
  ],
  // Documentation routes (external)
  "/docs": [
    { label: "Playground", href: "/" },
    { label: "Documentation", isCurrentPage: true }
  ],
  "/docs/introduction": [
    { label: "Playground", href: "/" },
    { label: "Documentation", href: "/docs" },
    { label: "Introduction", isCurrentPage: true }
  ],
  "/docs/getting-started": [
    { label: "Playground", href: "/" },
    { label: "Documentation", href: "/docs" },
    { label: "Get Started", isCurrentPage: true }
  ],
  "/docs/tutorials": [
    { label: "Playground", href: "/" },
    { label: "Documentation", href: "/docs" },
    { label: "Tutorials", isCurrentPage: true }
  ],
  // Settings routes
  "/settings": [
    { label: "Playground", href: "/" },
    { label: "Settings", isCurrentPage: true }
  ],
  "/settings/general": [
    { label: "Playground", href: "/" },
    { label: "Settings", href: "/settings" },
    { label: "General", isCurrentPage: true }
  ],
  "/settings/team": [
    { label: "Playground", href: "/" },
    { label: "Settings", href: "/settings" },
    { label: "Team", isCurrentPage: true }
  ],
  "/settings/billing": [
    { label: "Playground", href: "/" },
    { label: "Settings", href: "/settings" },
    { label: "Billing", isCurrentPage: true }
  ],
  "/settings/limits": [
    { label: "Playground", href: "/" },
    { label: "Settings", href: "/settings" },
    { label: "Limits", isCurrentPage: true }
  ],
};

// Fallback breadcrumb generation for dynamic routes
function generateFallbackBreadcrumbs(pathname: string): BreadcrumbItem[] {
  const segments = pathname.split("/").filter(Boolean);

  const breadcrumbs: BreadcrumbItem[] = [
    { label: "Playground", href: "/" }
  ];

  segments.forEach((segment, index) => {
    const href = "/" + segments.slice(0, index + 1).join("/");
    const isLast = index === segments.length - 1;

    // Convert kebab-case to Title Case
    const label = segment
      .split("-")
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");

    breadcrumbs.push({
      label,
      href: isLast ? undefined : href,
      isCurrentPage: isLast,
    });
  });

  return breadcrumbs;
}

export function useBreadcrumbs(): BreadcrumbItem[] {
  const location = useLocation();

  return useMemo(() => {
    const pathname = location.pathname;

    // Check if we have a specific configuration for this route
    if (routeConfig[pathname]) {
      return routeConfig[pathname];
    }

    // Generate fallback breadcrumbs for dynamic routes
    return generateFallbackBreadcrumbs(pathname);
  }, [location.pathname]);
}