import { test, expect } from "@playwright/test";
import { LIMITED_SESSION, mockCommonListEndpoints, seedSessionCookie } from "../mocks/api";
import { DUE_OVERDUE, TOWER_ID, mockBillingCyclesList, mockTowerDues } from "../mocks/billing";

/**
 * specs/03-maintenance-billing/frontend.md §4.2: "Flat Owner (non-admin)
 * role viewing /billing/dues sees the list in read-only mode — no 'Mark
 * Paid' action visible, per <Can permission='RECORD_PAYMENT'> gating."
 *
 * LIMITED_SESSION (VIEW_TOWER_DATA + MANAGE_ASSOCIATION_MEMBERS, no
 * RECORD_PAYMENT) is reused from Module 1's fixtures rather than adding a
 * near-duplicate "FlatOwner" session — it exercises the exact same
 * permission-gating rule (RECORD_PAYMENT absent → no Mark Paid action),
 * which is what this scenario is actually testing per
 * 00-architecture-and-standards.md §5.3 ("never a hardcoded role check").
 */
test("a session without RECORD_PAYMENT sees /billing/dues read-only, with no Mark Paid action", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await mockBillingCyclesList(page, []);
  await mockTowerDues(page, [DUE_OVERDUE]);
  await seedSessionCookie(page, LIMITED_SESSION);

  await page.goto(`/towers/${TOWER_ID}/billing/dues`);

  const table = page.getByRole("table");
  await expect(table.getByText(DUE_OVERDUE.flat_number)).toBeVisible();
  await expect(table.getByText("Overdue")).toBeVisible();
  await expect(page.getByRole("button", { name: "Mark Paid" })).toHaveCount(0);
});
