import { PERMISSIONS } from "@/lib/permissions";
import {
  Banknote,
  Building2,
  Calculator,
  CalendarClock,
  Home,
  KeyRound,
  Receipt,
  Settings,
  ShieldCheck,
  Users,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: (towerId: string) => string;
  icon: typeof Home;
  /** Permission required to see this item — never a hardcoded role check. */
  permission?: string;
}

/** Tower-scoped nav — rendered on every /towers/[towerId]/* route. */
export const TOWER_NAV_ITEMS: NavItem[] = [
  {
    label: "Dashboard",
    href: (towerId) => `/towers/${towerId}`,
    icon: Home,
    // Every tower member has at least VIEW_TOWER_DATA (association members
    // and flat owners alike) — see specs/00-architecture-and-standards.md §5.2.
    permission: PERMISSIONS.VIEW_TOWER_DATA,
  },
  {
    label: "Flats",
    href: (towerId) => `/towers/${towerId}/flats`,
    icon: KeyRound,
    // specs/02-flat-owner-tenant/frontend.md routes table: "Admin
    // (MANAGE_RESIDENTS or VIEW_TOWER_DATA)" — VIEW_TOWER_DATA is the
    // broader of the two so a read-only tower member (e.g. a custom role
    // with only VIEW_TOWER_DATA) still sees the nav item.
    permission: PERMISSIONS.VIEW_TOWER_DATA,
  },
  {
    label: "Tower Profile",
    href: (towerId) => `/towers/${towerId}/settings/tower-profile`,
    icon: Building2,
    permission: PERMISSIONS.MANAGE_COMPLEX,
  },
  {
    label: "Association Members",
    href: (towerId) => `/towers/${towerId}/settings/association-members`,
    icon: Users,
    permission: PERMISSIONS.MANAGE_ASSOCIATION_MEMBERS,
  },
  {
    label: "Roles",
    href: (towerId) => `/towers/${towerId}/settings/roles`,
    icon: ShieldCheck,
    permission: PERMISSIONS.MANAGE_ASSOCIATION_MEMBERS,
  },
  // Module 3 — Maintenance Billing (specs/03-maintenance-billing/frontend.md §1).
  // View access is VIEW_TOWER_DATA for all three; write actions (editing the
  // formula/grace period, generating a cycle, marking paid) are gated
  // per-screen via <Can> on CONFIGURE_BILLING / CREATE_BILLING_CYCLE /
  // RECORD_PAYMENT respectively — never hidden from view-only roles.
  {
    label: "Billing Formula",
    href: (towerId) => `/towers/${towerId}/billing/formula`,
    icon: Calculator,
    permission: PERMISSIONS.VIEW_TOWER_DATA,
  },
  {
    label: "Billing Cycles",
    href: (towerId) => `/towers/${towerId}/billing/cycles`,
    icon: CalendarClock,
    permission: PERMISSIONS.VIEW_TOWER_DATA,
  },
  {
    label: "Dues",
    href: (towerId) => `/towers/${towerId}/billing/dues`,
    icon: Receipt,
    permission: PERMISSIONS.VIEW_TOWER_DATA,
  },
  {
    // Module 4 — specs/04-special-collections-expenditure/frontend.md routes
    // table: "Admin: full; Flat Owner: read-only" — every tower member has
    // at least VIEW_TOWER_DATA, so gate on that (never MANAGE_SPECIAL_COLLECTIONS,
    // which would hide the read-only view from flat owners).
    label: "Special Collections",
    href: (towerId) => `/towers/${towerId}/special-collections`,
    icon: Banknote,
    permission: PERMISSIONS.VIEW_TOWER_DATA,
  },
  {
    label: "Expenditures",
    href: (towerId) => `/towers/${towerId}/expenditures`,
    icon: Receipt,
    permission: PERMISSIONS.VIEW_TOWER_DATA,
  },
];

export const SUPERUSER_NAV_ITEMS = [
  {
    label: "Complexes",
    href: "/admin/complexes",
    icon: Settings,
  },
];
