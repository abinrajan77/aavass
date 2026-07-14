import { TowerDashboardClient } from "./dashboard-client";

/**
 * `/towers/[towerId]` — app shell entry point per the routes table. The dashboard body
 * (stat cards, BentoGrid, activity feed) per specs/00-architecture-and-standards.md §3.2 —
 * previously an unclaimed placeholder (neither Module 1's scaffold nor Module 5's actual
 * spec ever built this screen, despite both referencing it).
 */
export default function TowerDashboardPage({ params }: { params: { towerId: string } }) {
  return <TowerDashboardClient towerId={params.towerId} />;
}
