import type { Page, Route } from "@playwright/test";
import type { LoginResponse } from "@/lib/api/types";

/**
 * Mocked backend fixtures for the Module 1 frontend test plan.
 *
 * There is no live backend in this repo yet (built concurrently by another
 * agent to specs/01-auth-rbac-tower-setup/backend.md) — every route here is
 * intercepted client-side via `page.route()` against
 * `NEXT_PUBLIC_API_BASE_URL=http://localhost:3100/__mock_api__` (see
 * playwright.config.ts). Swap this file's mocks out once the backend is
 * live; the tests themselves assert on rendered UI and should keep passing.
 */
export const MOCK_API_PREFIX = "**/__mock_api__/**";

export const TOWER_A = { tower_id: "tower-a", tower_name: "Oakwood Tower", role_name: "Admin" };
export const TOWER_B = { tower_id: "tower-b", tower_name: "Sunset Tower", role_name: "Treasurer" };

export const SUPERUSER_SESSION: LoginResponse = {
  user: { id: "user-super", email: "super@aavaas.internal", account_type: "tower_admin", is_superuser: true },
  permissions: [],
  towers: [],
};

export const ADMIN_SESSION: LoginResponse = {
  user: { id: "user-1", email: "admin@oakwood.test", account_type: "tower_admin", is_superuser: false, name: "Asha Admin" },
  permissions: [
    "MANAGE_COMPLEX",
    "MANAGE_ASSOCIATION_MEMBERS",
    "MANAGE_RESIDENTS",
    "CONFIGURE_BILLING",
    "CREATE_BILLING_CYCLE",
    "RECORD_PAYMENT",
    "MANAGE_SPECIAL_COLLECTIONS",
    "MANAGE_EXPENDITURE",
    "VIEW_REPORTS",
    "VIEW_TOWER_DATA",
  ],
  towers: [TOWER_A, TOWER_B],
};

/** A member holding a custom role with only VIEW_TOWER_DATA + MANAGE_ASSOCIATION_MEMBERS. */
export const LIMITED_SESSION: LoginResponse = {
  user: {
    id: "user-2",
    email: "secretary@oakwood.test",
    account_type: "tower_admin",
    is_superuser: false,
    name: "Sam Secretary",
  },
  permissions: ["VIEW_TOWER_DATA", "MANAGE_ASSOCIATION_MEMBERS"],
  towers: [TOWER_A],
};

export async function seedSessionCookie(page: Page, session: LoginResponse) {
  await page.context().addCookies([
    {
      name: "aavaas_session",
      value: JSON.stringify(session),
      url: "http://localhost:3100",
    },
  ]);
}

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

/** Common list-endpoint fallbacks so pages under test don't error on unrelated fetches. */
export async function mockCommonListEndpoints(page: Page) {
  await page.route(`${MOCK_API_PREFIX}/roles*`, (route) =>
    json(route, {
      items: [
        { id: "role-admin", tower_id: "tower-a", name: "Admin", is_system_default: true, permission_codes: [], deactivated_at: null },
      ],
      page: 1,
      page_size: 100,
      total: 1,
    })
  );
  await page.route(`${MOCK_API_PREFIX}/association-members*`, (route) =>
    json(route, { items: [], page: 1, page_size: 100, total: 0 })
  );
  await page.route(`${MOCK_API_PREFIX}/towers/*`, async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    await json(route, {
      id: "tower-a",
      complex_id: "complex-1",
      name: "Oakwood Tower",
      code: "OAK",
      total_floors: 10,
      total_flats: 40,
      association_name: "Oakwood Owners Association",
      deactivated_at: null,
      created_at: new Date().toISOString(),
    });
  });
  await page.route(`${MOCK_API_PREFIX}/complexes*`, (route) =>
    json(route, { items: [], page: 1, page_size: 100, total: 0 })
  );
}

export async function mockLogin(page: Page, session: LoginResponse) {
  await page.route(`${MOCK_API_PREFIX}/auth/login`, (route) => json(route, session));
}

/**
 * Module 2 (specs/02-flat-owner-tenant) fixtures. Flat owners aren't
 * association members (specs/00-architecture-and-standards.md §5.2), so
 * their session carries an empty `towers` list and the flat_owner account
 * type instead.
 */
export const OWNER_USER_ID = "user-owner-1";

export const OWNER_SESSION: LoginResponse = {
  user: {
    id: OWNER_USER_ID,
    email: "priya@owner.test",
    account_type: "flat_owner",
    is_superuser: false,
    name: "Priya Owner",
  },
  permissions: ["VIEW_TOWER_DATA", "MANAGE_OWN_FLAT"],
  towers: [],
};

export { json as fulfillJson };
