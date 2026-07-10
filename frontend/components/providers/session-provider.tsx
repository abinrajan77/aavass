"use client";

import { createContext, useContext } from "react";
import type { Session } from "@/lib/session";

const SessionContext = createContext<Session | null>(null);

export function SessionProvider({
  session,
  children,
}: {
  session: Session | null;
  children: React.ReactNode;
}) {
  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>;
}

/** Client-side counterpart to the server `session.permissions` helper (specs §5.3). */
export function useSession(): Session | null {
  return useContext(SessionContext);
}
