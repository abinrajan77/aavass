import { api } from "./client";
import type { AuditLogEntry, Paginated, TowerDashboardStats } from "./types";

/**
 * Tower admin dashboard — GET .../dashboard-stats (new aggregate endpoint) and the existing
 * GET .../audit-log (specs/01-auth-rbac-tower-setup/backend.md, already built by Module 1)
 * reused as-is for the "recent activity" feed per that spec's frontend.md note that this
 * module only needed to expose the data for the dashboard to consume.
 */

export function getTowerDashboardStats(towerId: string) {
  return api.get<TowerDashboardStats>(`/api/v1/towers/${towerId}/dashboard-stats`);
}

export function getRecentActivity(towerId: string, pageSize = 8) {
  return api.get<Paginated<AuditLogEntry>>(`/api/v1/towers/${towerId}/audit-log`, {
    params: { page: 1, page_size: pageSize },
  });
}
