"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Minimal reimplementation of magicui's `NumberTicker` (magicui.design) — see
 * components/magicui/shine-border.tsx's doc comment for why this is
 * hand-rolled rather than an npm dependency (no `framer-motion` dependency
 * in this repo either, which the real component uses). Animates from 0 to
 * `value` whenever `value` changes; used per
 * specs/00-architecture-and-standards.md §3.2 ("NumberTicker — animated
 * counters on dashboard stat cards") on the special-collection detail page's
 * headline collected-amount figure (frontend.md).
 */
export function NumberTicker({
  value,
  decimalPlaces = 0,
  durationMs = 600,
  className,
}: {
  value: number;
  decimalPlaces?: number;
  durationMs?: number;
  className?: string;
}) {
  const [display, setDisplay] = React.useState(0);

  React.useEffect(() => {
    let raf: number;
    const start = performance.now();

    function tick(now: number) {
      const progress = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(value * eased);
      if (progress < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        setDisplay(value);
      }
    }

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, durationMs]);

  return (
    <span className={cn("tabular-nums", className)}>
      {new Intl.NumberFormat("en-IN", {
        minimumFractionDigits: decimalPlaces,
        maximumFractionDigits: decimalPlaces,
      }).format(display)}
    </span>
  );
}
