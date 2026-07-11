"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CollectionReportTab } from "@/components/reports/collection-report-tab";
import { OutstandingDuesReportTab } from "@/components/reports/outstanding-dues-report-tab";
import { ExpenditureReportTab } from "@/components/reports/expenditure-report-tab";
import { CollectionVsExpenditureTab } from "@/components/reports/collection-vs-expenditure-tab";
import { TenantRegisterTab } from "@/components/reports/tenant-register-tab";

const TAB_VALUES = [
  "collection",
  "outstanding_dues",
  "expenditure",
  "collection_vs_expenditure",
  "tenant_register",
] as const;
type TabValue = (typeof TAB_VALUES)[number];

function isTabValue(value: string | null): value is TabValue {
  return TAB_VALUES.includes(value as TabValue);
}

/**
 * `/towers/[towerId]/reports` — specs/05-reporting-owner-portal-notifications/
 * frontend.md §2: "Tab state in the URL (`?tab=collection`) so a link to a
 * specific report is shareable/bookmarkable." Mirrors the same
 * usePathname/useSearchParams/router.replace pattern already used by
 * `app/(app)/towers/[towerId]/billing/dues/dues-client.tsx`'s cycle filter.
 */
export function ReportsClient({ towerId }: { towerId: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const tabParam = searchParams.get("tab");
  const activeTab: TabValue = isTabValue(tabParam) ? tabParam : "collection";

  function handleTabChange(value: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", value);
    router.replace(`${pathname}?${params.toString()}`);
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-foreground">Reports</h1>
        <p className="text-sm text-muted-foreground">
          Collection, dues, expenditure and tenancy reports for this tower.
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList>
          <TabsTrigger value="collection">Monthly Collection</TabsTrigger>
          <TabsTrigger value="outstanding_dues">Outstanding Dues</TabsTrigger>
          <TabsTrigger value="expenditure">Expenditure</TabsTrigger>
          <TabsTrigger value="collection_vs_expenditure">Collection vs Expenditure</TabsTrigger>
          <TabsTrigger value="tenant_register">Tenant Register</TabsTrigger>
        </TabsList>
        <TabsContent value="collection">
          <CollectionReportTab towerId={towerId} />
        </TabsContent>
        <TabsContent value="outstanding_dues">
          <OutstandingDuesReportTab towerId={towerId} />
        </TabsContent>
        <TabsContent value="expenditure">
          <ExpenditureReportTab towerId={towerId} />
        </TabsContent>
        <TabsContent value="collection_vs_expenditure">
          <CollectionVsExpenditureTab towerId={towerId} />
        </TabsContent>
        <TabsContent value="tenant_register">
          <TenantRegisterTab towerId={towerId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
