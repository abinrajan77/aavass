import { api } from "./client";
import type { JobStatusResponse } from "./types";

/**
 * Shared canonical async-job status route — 06-cloud-devops.md §4: "one
 * polling route/hook for every module's async jobs, not a module-specific
 * path." Module 3 uses this for billing-cycle generation beyond ~300 flats
 * (specs/03-maintenance-billing/backend.md §4); future modules reuse it
 * unchanged rather than growing their own polling endpoint.
 */
export function getJobStatus(towerId: string, jobId: string) {
  return api.get<JobStatusResponse>(`/api/v1/towers/${towerId}/jobs/${jobId}`);
}
