import { test, expect } from "@playwright/test";
import {
  ADMIN_SESSION,
  MOCK_API_PREFIX,
  mockCommonListEndpoints,
  seedSessionCookie,
  TOWER_A,
} from "../mocks/api";

/**
 * specs/01-auth-rbac-tower-setup/frontend.md frontend test plan:
 * "Creating a custom role via the permission checkbox matrix, then inviting
 * a new association member with that role, then logging in as that member
 * shows exactly the granted permissions' worth of UI — nothing more."
 *
 * Step 1 (as an Admin) exercises the actual role-creation UI/checkbox
 * matrix against a mocked POST /roles. Step 2 simulates "logging in as that
 * member" by seeding a session mirroring exactly the permissions selected in
 * step 1 (VIEW_TOWER_DATA + MANAGE_ASSOCIATION_MEMBERS only) and asserting
 * the resulting nav — the full round trip through a real invite/login flow
 * needs the live backend, which isn't available in this repo state yet.
 */
test("custom role created via the checkbox matrix, then that role's permissions drive the nav after login", async ({
  page,
}) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  await page.route(`${MOCK_API_PREFIX}/roles`, async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        id: "role-secretary",
        tower_id: TOWER_A.tower_id,
        name: "Secretary",
        is_system_default: false,
        permission_codes: ["VIEW_TOWER_DATA", "MANAGE_ASSOCIATION_MEMBERS"],
        deactivated_at: null,
      }),
    });
  });

  await page.goto(`/towers/${TOWER_A.tower_id}/settings/roles`);
  await page.getByRole("button", { name: "Create role" }).click();

  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Role name").fill("Secretary");
  await dialog.getByText("VIEW_TOWER_DATA", { exact: true }).click();
  await dialog.getByText("MANAGE_ASSOCIATION_MEMBERS", { exact: true }).click();
  await dialog.getByRole("button", { name: "Create role" }).click();

  await expect(page.getByText("Role created")).toBeVisible();

  // "Logging in as that member": a fresh session mirroring exactly the
  // Secretary role's two permissions.
  await seedSessionCookie(page, {
    user: {
      id: "user-secretary",
      email: "secretary@oakwood.test",
      account_type: "tower_admin",
      is_superuser: false,
      name: "New Secretary",
    },
    permissions: ["VIEW_TOWER_DATA", "MANAGE_ASSOCIATION_MEMBERS"],
    towers: [TOWER_A],
  });

  await page.goto(`/towers/${TOWER_A.tower_id}`);
  await expect(page.getByRole("link", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Association Members" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Roles" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Tower Profile" })).toHaveCount(0);
});
