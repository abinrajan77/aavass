import { Badge } from "@/components/ui/badge";
import type { OccupancyStatus } from "@/lib/api/types";

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

/**
 * Occupancy-status badge — specs/02-flat-owner-tenant/frontend.md:
 *   - Vacant -> muted / outline gray (reuses the shared table's Vacant row as-is).
 *   - Tenant-occupied -> accent (gold) solid.
 *   - Owner-occupied -> secondary (navy-tinted) outline, the neutral default.
 *
 * Deliberately NOT a single `<StatusBadge kind="occupancy" | "payment">`
 * component with one shared string-keyed variant map: `OccupancyStatus`
 * (owner_occupied/tenant_occupied/vacant) and `PaymentStatus`
 * (Paid/Pending/Overdue/Vacant) are disjoint TypeScript string-literal
 * unions, so passing an occupancy value into `PaymentStatusBadge` (or vice
 * versa) is a *compile-time* type error, not just a convention someone could
 * forget to follow at runtime — this is a stronger structural guarantee
 * against the success/warning/destructive-reuse regression than a shared
 * `kind` prop would give (nothing stops `kind="payment"` being called with
 * an occupancy string under a permissive `kind: string` prop). See the
 * frontend agent's final report for the full rationale.
 */
const OCCUPANCY_STATUS_LABEL: Record<OccupancyStatus, string> = {
  vacant: "Vacant",
  tenant_occupied: "Tenant-occupied",
  owner_occupied: "Owner-occupied",
};

const OCCUPANCY_STATUS_VARIANT: Record<OccupancyStatus, "mutedOutline" | "accent" | "secondaryOutline"> = {
  vacant: "mutedOutline",
  tenant_occupied: "accent",
  owner_occupied: "secondaryOutline",
};

export function OccupancyStatusBadge({ status }: { status: OccupancyStatus }) {
  return <Badge variant={OCCUPANCY_STATUS_VARIANT[status]}>{OCCUPANCY_STATUS_LABEL[status]}</Badge>;
}
