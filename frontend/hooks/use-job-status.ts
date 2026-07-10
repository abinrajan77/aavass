import { useQuery } from "@tanstack/react-query";
import { getJobStatus } from "@/lib/api/jobs";
import type { JobStatusResponse } from "@/lib/api/types";

/**
 * Shared canonical job-status polling hook — 06-cloud-devops.md §4: "one
 * polling route/hook for every module's async jobs, not a module-specific
 * path." Used today for billing-cycle generation beyond ~300 flats
 * (specs/03-maintenance-billing/frontend.md §2.3), reusable unchanged by any
 * future module's async job.
 *
 * Polls every 2s (per frontend.md §2.3: "polls ... every 2s") while
 * `enabled` and the last known status is not yet terminal.
 */
export function useJobStatus(
  towerId: string,
  jobId: string | null,
  options?: { enabled?: boolean; onDone?: (result: JobStatusResponse) => void; onFailed?: (result: JobStatusResponse) => void }
) {
  const enabled = Boolean(jobId) && (options?.enabled ?? true);

  return useQuery({
    queryKey: ["job-status", towerId, jobId],
    queryFn: async () => {
      const result = await getJobStatus(towerId, jobId as string);
      if (result.status === "done") options?.onDone?.(result);
      if (result.status === "failed") options?.onFailed?.(result);
      return result;
    },
    enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "done" || status === "failed" ? false : 2000;
    },
  });
}
