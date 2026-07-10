/**
 * Public (unauthenticated) route group — login/forgot-password/reset-password.
 * Theme: "full-bleed bg-primary (deep navy) background, a centered Card" —
 * see 01-auth-rbac-tower-setup/frontend.md "Theme application".
 */
export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-primary px-4 py-12">
      {children}
    </div>
  );
}
