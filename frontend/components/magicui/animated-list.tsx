"use client";

import { Children, isValidElement, useEffect, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * magicui `AnimatedList` — specs/00-architecture-and-standards.md §3.2:
 * "recent activity / audit-log feed (payment recorded, formula changed,
 * tenant added)." Did not exist in this repo before this module — built here
 * from scratch, matching the hand-rolled, dependency-free style of the two
 * magicui components that already exist (`number-ticker.tsx`, `shine-
 * border.tsx`): no magicui npm package is vendored (copy-paste, like
 * shadcn/ui) and no framer-motion dependency in this repo (see
 * `number-ticker.tsx`'s doc-comment) — this uses a plain CSS opacity/
 * transform transition staggered per item via `transitionDelay`, not a JS
 * animation library.
 *
 * Used by specs/05-reporting-owner-portal-notifications/frontend.md §3 (the
 * notification-preview screen) to render the drafted message(s) "as a queue
 * — one card per recipient", staggered in on mount.
 */
export function AnimatedList({
  children,
  className,
  itemClassName,
  delayMs = 150,
}: {
  children: React.ReactNode;
  className?: string;
  itemClassName?: string;
  /** Stagger delay between successive items mounting in, in ms. */
  delayMs?: number;
}) {
  const items = Children.toArray(children).filter(isValidElement);

  // Flips true one animation frame after mount so the browser paints the
  // "before" state (opacity 0, translated down) first, then transitions to
  // the "after" state — without this the CSS transition has no starting
  // frame to animate from and the items would just snap straight in.
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const raf = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div className={cn("flex flex-col gap-3", className)} data-testid="animated-list">
      {items.map((item, index) => (
        <div
          key={item.key ?? index}
          data-testid="animated-list-item"
          className={cn("transition-all duration-500 ease-out", itemClassName)}
          style={{
            transitionDelay: `${index * delayMs}ms`,
            opacity: mounted ? 1 : 0,
            transform: mounted ? "translateY(0)" : "translateY(12px)",
          }}
        >
          {item}
        </div>
      ))}
    </div>
  );
}
