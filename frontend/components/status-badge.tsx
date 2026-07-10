import { Badge } from "@/components/ui/badge";

/**
 * Payment-status badge — Paid/Pending/Overdue/Vacant map to
 * success/warning/destructive/muted per specs/00-architecture-and-standards.md
 * §3.1. Owned by Modules 3/4/5; kept here only as the shared, spec-correct
 * mapping other modules can import instead of re-deriving ad-hoc colors.
 */
export type PaymentStatus = "Paid" | "Pending" | "Overdue" | "Vacant";

const PAYMENT_STATUS_VARIANT: Record<PaymentStatus, "success" | "warning" | "destructive" | "mutedOutline"> = {
  Paid: "success",
  Pending: "warning",
  Overdue: "destructive",
  Vacant: "mutedOutline",
};

export function PaymentStatusBadge({ status }: { status: PaymentStatus }) {
  return <Badge variant={PAYMENT_STATUS_VARIANT[status]}>{status}</Badge>;
}

/**
 * Active/Deactivated indicator for non-payment entities (association
 * members, roles, towers, complexes) — per the "Theme application" section:
 * these must NOT reuse the payment-status tokens. Active renders as plain
 * text (no badge); deactivated renders as a muted outline badge.
 */
export function ActiveStateBadge({ deactivatedAt }: { deactivatedAt: string | null }) {
  if (!deactivatedAt) {
    return <span className="text-sm text-foreground">Active</span>;
  }
  return <Badge variant="mutedOutline">Deactivated</Badge>;
}
