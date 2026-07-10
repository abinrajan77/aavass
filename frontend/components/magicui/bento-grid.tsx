import { cn } from "@/lib/utils";

/**
 * magicui `BentoGrid` — specs/00-architecture-and-standards.md §3.2: "layout
 * for the Tower Admin dashboard (stat cards + quick links in an asymmetric
 * grid)." No magicui npm package is vendored (copy-paste component, like
 * shadcn/ui) — minimal reimplementation, no external animation dependency.
 */
export function BentoGrid({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("grid grid-cols-1 gap-4 sm:grid-cols-3", className)}>{children}</div>;
}

export function BentoCard({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm",
        className
      )}
    >
      {children}
    </div>
  );
}
