import { test, expect } from "@playwright/test";
import { LIMITED_SESSION, mockCommonListEndpoints, seedSessionCookie } from "../mocks/api";

/**
 * specs/01-auth-rbac-tower-setup/frontend.md frontend test plan:
 * "Attempting to navigate directly (via URL) to a
 * /towers/{otherTowerId}/settings/roles the user isn't a member of redirects
 * to a 'not authorized' state rather than rendering a blank or
 * partially-loaded page."
 *
 * LIMITED_SESSION only belongs to tower-a; direct-navigating to tower-b must
 * redirect, not render.
 */
test("direct URL to a tower the user isn't a member of redirects to /not-authorized", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, LIMITED_SESSION);

  await page.goto("/towers/tower-b/settings/roles");

  await expect(page).toHaveURL(/\/not-authorized/);
  await expect(page.getByText("You don't have access to this page")).toBeVisible();
});
