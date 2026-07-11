import { PaymentStatusBadge } from "@/components/status-badge";

/**
 * Maps a report row's lowercase `status` (`"paid" | "pending" | "overdue"`,
 * per backend.md's `CollectionReportRow`/dashboard schemas) to the shared
 * `PaymentStatusBadge` — reused across the Monthly Collection report tab and
 * the owner dashboard's current-due/payment-history cells so the
 * success/warning/destructive token mapping from
 * specs/00-architecture-and-standards.md §3.1 is defined exactly once for
 * this module, never re-derived ad-hoc per screen.
 */
const STATUS_LABEL = {
  paid: "Paid",
  pending: "Pending",
  overdue: "Overdue",
} as const;

export function ReportStatusBadge({ status }: { status: "paid" | "pending" | "overdue" }) {
  return <PaymentStatusBadge status={STATUS_LABEL[status]} />;
}
