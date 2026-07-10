import { BentoCard, BentoGrid } from "@/components/magicui/bento-grid";
import { NumberTicker } from "@/components/magicui/number-ticker";

/**
 * Standalone, presentation-only stat cards — specs/03-maintenance-billing/frontend.md
 * §2.4: "Build this as a standalone, exported component
 * (components/billing/BillingStatCards.tsx) taking
 * { totalCollected, pendingCount, overdueAmount } as props — Module 5's
 * admin dashboard reuses this exact component for the tower-wide
 * (cross-cycle) equivalent, so keep it free of cycle-specific data-fetching
 * logic (fetch happens in the parent page, component only renders)."
 *
 * Deliberately has NO useQuery/useMutation/fetch of its own — the parent
 * page (cycle detail today, Module 5's admin dashboard later) is
 * responsible for supplying these three numbers from whichever scope
 * (single cycle vs tower-wide) it represents.
 */
export interface BillingStatCardsProps {
  totalCollected: number;
  pendingCount: number;
  overdueAmount: number;
  /** Optional overrides for card titles — Module 5 may want tower-wide labels. */
  labels?: {
    totalCollected?: string;
    pendingCount?: string;
    overdueAmount?: string;
  };
}

export function BillingStatCards({ totalCollected, pendingCount, overdueAmount, labels }: BillingStatCardsProps) {
  return (
    <BentoGrid>
      <BentoCard>
        <p className="text-sm font-medium text-muted-foreground">
          {labels?.totalCollected ?? "Total Collected This Cycle"}
        </p>
        <p className="mt-2 text-2xl font-semibold text-foreground">
          <NumberTicker value={totalCollected} decimalPlaces={2} prefix="₹" />
        </p>
      </BentoCard>
      <BentoCard>
        <p className="text-sm font-medium text-muted-foreground">{labels?.pendingCount ?? "Pending Count"}</p>
        <p className="mt-2 text-2xl font-semibold text-warning">
          <NumberTicker value={pendingCount} />
        </p>
      </BentoCard>
      <BentoCard>
        <p className="text-sm font-medium text-muted-foreground">
          {labels?.overdueAmount ?? "Overdue Amount"}
        </p>
        <p className="mt-2 text-2xl font-semibold text-destructive">
          <NumberTicker value={overdueAmount} decimalPlaces={2} prefix="₹" />
        </p>
      </BentoCard>
    </BentoGrid>
  );
}
