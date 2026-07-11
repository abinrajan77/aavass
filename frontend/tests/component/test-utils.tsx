import type { ReactElement, ReactNode } from "react";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SessionProvider } from "@/components/providers/session-provider";
import type { Session } from "@/lib/session";

/**
 * Shared RTL render helper for Module 4's component tests
 * (specs/04-special-collections-expenditure/frontend.md "Component tests
 * (Vitest/RTL)"). Wraps a fresh, retry-disabled QueryClient (components under
 * test use TanStack Query mutations/queries) and, optionally, a fake
 * `SessionProvider` for components gated by `<Can>`.
 */
export function renderWithProviders(
  ui: ReactElement,
  { session = null }: { session?: Session | null } = {}
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <SessionProvider session={session}>{children}</SessionProvider>
      </QueryClientProvider>
    );
  }

  return render(ui, { wrapper: Wrapper });
}

export const FAKE_ADMIN_SESSION: Session = {
  user: {
    id: "user-1",
    email: "admin@oakwood.test",
    account_type: "tower_admin",
    is_superuser: false,
    name: "Asha Admin",
  },
  permissions: ["MANAGE_SPECIAL_COLLECTIONS", "MANAGE_EXPENDITURE", "VIEW_TOWER_DATA", "RECORD_PAYMENT"],
  towers: [{ tower_id: "tower-a", tower_name: "Oakwood Tower", role_name: "Admin" }],
};
