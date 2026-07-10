"use client";

import { useRouter } from "next/navigation";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

/**
 * Formula/Grace-Period `Tabs` navigation — frontend.md §2.2: "shown as a
 * Tabs sibling of the formula page (Tabs: 'Formula' / 'Grace Period')."
 * These are two separate routes (not a single page with client-side-only
 * tab state) so each is independently linkable/bookmarkable; the `Tabs`
 * component here is just the visual affordance, navigating via the router
 * on change.
 */
export function BillingConfigTabs({ towerId, active }: { towerId: string; active: "formula" | "grace-period" }) {
  const router = useRouter();

  return (
    <Tabs
      value={active}
      onValueChange={(value) => router.push(`/towers/${towerId}/billing/${value}`)}
    >
      <TabsList>
        <TabsTrigger value="formula">Formula</TabsTrigger>
        <TabsTrigger value="grace-period">Grace Period</TabsTrigger>
      </TabsList>
    </Tabs>
  );
}
