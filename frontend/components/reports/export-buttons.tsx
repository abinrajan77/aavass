"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useJobStatus } from "@/hooks/use-job-status";
import { ApiError } from "@/lib/api/client";
import { exportReport, type ReportFormat, type ReportType } from "@/lib/api/reports";
import { downloadBlob } from "@/lib/utils";

/**
 * Shared "Export PDF" / "Export CSV" control for all 5 reports —
 * specs/05-reporting-owner-portal-notifications/frontend.md §2:
 *   - <=5000 rows: backend streams the file synchronously (200) -> trigger a
 *     browser download immediately from the in-memory `Blob`.
 *   - >5000 rows: backend returns `202 { job_id }` -> switch to a disabled
 *     "Preparing export…" state with a `Skeleton`, poll the shared canonical
 *     `GET /towers/{tower_id}/jobs/{job_id}` route (via `useJobStatus`,
 *     already built by Module 3) every 2s, and on `done` open the pre-signed
 *     `result.download_url` (same `window.open` pattern already used for
 *     receipt/attachment downloads elsewhere in this app — see
 *     `components/billing/dues-data-table.tsx` /
 *     `expenditures-client.tsx`), with a Sonner toast on done/failed.
 */
export function ExportButtons({
  towerId,
  reportType,
  params,
  disabled,
}: {
  towerId: string;
  reportType: ReportType;
  params: Record<string, string | number | boolean | undefined>;
  /** Disable both buttons — e.g. no billing cycle selected yet. */
  disabled?: boolean;
}) {
  const [pendingFormat, setPendingFormat] = useState<ReportFormat | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobFormat, setJobFormat] = useState<ReportFormat | null>(null);

  useJobStatus(towerId, jobId, {
    enabled: Boolean(jobId),
    onDone: (result) => {
      const url = result.result?.download_url;
      if (url) {
        window.open(url, "_blank", "noopener,noreferrer");
        toast.success("Export ready");
      } else {
        toast.error("Export finished but no file was returned");
      }
      setJobId(null);
      setJobFormat(null);
      setPendingFormat(null);
    },
    onFailed: () => {
      toast.error("Export failed — try again", {
        action: { label: "Retry", onClick: () => void handleExport(jobFormat ?? "pdf") },
      });
      setJobId(null);
      setJobFormat(null);
      setPendingFormat(null);
    },
  });

  async function handleExport(format: ReportFormat) {
    setPendingFormat(format);
    try {
      const result = await exportReport(towerId, reportType, format, params);
      if (result.kind === "file") {
        downloadBlob(result.blob, result.filename);
        setPendingFormat(null);
      } else {
        setJobId(result.jobId);
        setJobFormat(format);
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Couldn't export the report";
      toast.error(message);
      setPendingFormat(null);
    }
  }

  if (jobId) {
    return (
      <div className="flex items-center gap-2" data-testid="export-preparing">
        <Skeleton className="h-9 w-36" />
        <span className="text-sm text-muted-foreground">
          Preparing {jobFormat?.toUpperCase()} export…
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled || pendingFormat !== null}
        onClick={() => void handleExport("pdf")}
      >
        <Download className="mr-2 h-4 w-4" />
        {pendingFormat === "pdf" ? "Exporting…" : "Export PDF"}
      </Button>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled || pendingFormat !== null}
        onClick={() => void handleExport("csv")}
      >
        <Download className="mr-2 h-4 w-4" />
        {pendingFormat === "csv" ? "Exporting…" : "Export CSV"}
      </Button>
    </div>
  );
}
