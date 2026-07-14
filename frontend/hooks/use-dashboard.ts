import { useQuery } from "@tanstack/react-query";
import { getRecentActivity, getTowerDashboardStats } from "@/lib/api/dashboard";

export function useTowerDashboardStats(towerId: string) {
  return useQuery({
    queryKey: ["tower-dashboard-stats", towerId],
    queryFn: () => getTowerDashboardStats(towerId),
  });
}

export function useRecentActivity(towerId: string) {
  return useQuery({
    queryKey: ["tower-recent-activity", towerId],
    queryFn: () => getRecentActivity(towerId),
  });
}
