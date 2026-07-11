import type { LoginResponse } from "./api/types";

/**
 * Permission catalog — mirrors specs/00-architecture-and-standards.md §5.1.
 *
 * These are opaque string codes checked against `session.permissions`. Never
 * hardcode a role name (e.g. `role === "Admin"`) to gate UI — always check a
 * permission code so a future custom role with a subset of Admin's
 * permissions still renders the correct partial nav/UI, per
 * 01-auth-rbac-tower-setup/frontend.md "What must NOT break".
 *
 * IMPORTANT: this is a UX-only convenience layer. The real security boundary
 * is the backend's `require_permission()` FastAPI dependency (see
 * specs/00-architecture-and-standards.md §5.3). Nothing here should be
 * treated as authoritative.
 */
export const PERMISSIONS = {
  MANAGE_COMPLEX: "MANAGE_COMPLEX",
  MANAGE_ASSOCIATION_MEMBERS: "MANAGE_ASSOCIATION_MEMBERS",
  MANAGE_RESIDENTS: "MANAGE_RESIDENTS",
  CONFIGURE_BILLING: "CONFIGURE_BILLING",
  CREATE_BILLING_CYCLE: "CREATE_BILLING_CYCLE",
  RECORD_PAYMENT: "RECORD_PAYMENT",
  MANAGE_SPECIAL_COLLECTIONS: "MANAGE_SPECIAL_COLLECTIONS",
  MANAGE_EXPENDITURE: "MANAGE_EXPENDITURE",
  VIEW_REPORTS: "VIEW_REPORTS",
  VIEW_TOWER_DATA: "VIEW_TOWER_DATA",
  MANAGE_OWN_FLAT: "MANAGE_OWN_FLAT",
} as const;

export type Permission = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];

/** Full catalog with descriptions, for rendering the role permission checkbox matrix. */
export const PERMISSION_CATALOG: { code: Permission; description: string }[] = [
  { code: PERMISSIONS.MANAGE_COMPLEX, description: "Create/edit complex & tower records" },
  {
    code: PERMISSIONS.MANAGE_ASSOCIATION_MEMBERS,
    description: "Add/edit association members, assign roles",
  },
  { code: PERMISSIONS.MANAGE_RESIDENTS, description: "Add/edit flats, owners, tenants" },
  { code: PERMISSIONS.CONFIGURE_BILLING, description: "Edit maintenance formula & grace period" },
  { code: PERMISSIONS.CREATE_BILLING_CYCLE, description: "Generate a billing cycle" },
  { code: PERMISSIONS.RECORD_PAYMENT, description: "Mark dues paid, generate receipts" },
  {
    code: PERMISSIONS.MANAGE_SPECIAL_COLLECTIONS,
    description: "Create/edit special collections",
  },
  { code: PERMISSIONS.MANAGE_EXPENDITURE, description: "Record tower/complex expenditure" },
  { code: PERMISSIONS.VIEW_REPORTS, description: "Generate/export reports" },
  {
    code: PERMISSIONS.VIEW_TOWER_DATA,
    description: "Read-only tower-wide visibility (flat owners get this by default)",
  },
  {
    code: PERMISSIONS.MANAGE_OWN_FLAT,
    description: "Flat owner: edit own contact/tenant/occupancy details",
  },
];

/**
 * Client-safe permission check — a superuser bypasses every tower-level
 * permission (mirroring the backend's `require_permission()` bypass, see
 * `00-architecture-and-standards.md` §5.3), since `session.permissions` is
 * always `[]` for a superuser (they're not an `AssociationMember`, so no
 * tower role/permission set applies to them). Without this bypass, nav
 * items and `<Can>`-gated actions silently disappear for a superuser even
 * though the backend grants them full access.
 *
 * `lib/session.ts` has an equivalent `hasPermission()`, but that module is
 * `server-only` and can't be imported from client components like
 * `components/shell/sidebar-nav.tsx` / `components/auth/can.tsx` — this is
 * the client-safe counterpart both use.
 */
export function hasPermission(session: LoginResponse | null, permission: string): boolean {
  if (!session) return false;
  return session.user.is_superuser || session.permissions.includes(permission);
}
