import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * `/towers/[towerId]` — app shell entry point per the routes table. The
 * dashboard *body* (stat cards, BentoGrid, activity feed, etc.) is owned by
 * Module 5 (specs/05-reporting-owner-portal-notifications/frontend.md) and
 * should replace this placeholder card — Module 1 only guarantees the shell
 * (Sidebar/Breadcrumb/Command/Avatar) renders correctly around it.
 */
export default function TowerDashboardPage({ params }: { params: { towerId: string } }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Dashboard</CardTitle>
        <CardDescription>
          Placeholder — the tower dashboard (stat cards, activity feed) is built by Module 5.
        </CardDescription>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground">
        Tower ID: <code className="rounded bg-muted px-1 py-0.5">{params.towerId}</code>
      </CardContent>
    </Card>
  );
}
