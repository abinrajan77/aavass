"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * magicui `NumberTicker` — specs/00-architecture-and-standards.md §3.2:
 * "animated counters on dashboard stat cards (total collected this month,
 * pending dues count, overdue amount)." No magicui npm package is vendored
 * in this repo (magicui components are copy-paste, like shadcn/ui) — this is
 * a minimal, dependency-free reimplementation: animates from 0 to `value`
 * with a simple eased rAF loop, no framer-motion needed.
 *
 * Must render correctly (no crash, no NaN/"undefined") at `value = 0` —
 * specs/03-maintenance-billing/frontend.md §4.1: "renders correctly with
 * zero-value props... without crashing the NumberTicker animation."
 */
export function NumberTicker({
  value,
  className,
  decimalPlaces = 0,
  prefix = "",
  suffix = "",
  duration = 600,
}: {
  value: number;
  className?: string;
  decimalPlaces?: number;
  prefix?: string;
  suffix?: string;
  /** Animation duration in ms. */
  duration?: number;
}) {
  const safeValue = Number.isFinite(value) ? value : 0;
  const [display, setDisplay] = useState(0);
  const frameRef = useRef<number>();

  useEffect(() => {
    const start = performance.now();
    const from = 0;

    function tick(now: number) {
      const elapsed = now - start;
      const progress = Math.min(1, elapsed / duration);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(from + (safeValue - from) * eased);
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(tick);
      } else {
        setDisplay(safeValue);
      }
    }

    frameRef.current = requestAnimationFrame(tick);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [safeValue, duration]);

  return (
    <span className={cn("tabular-nums", className)}>
      {prefix}
      {display.toLocaleString("en-IN", {
        minimumFractionDigits: decimalPlaces,
        maximumFractionDigits: decimalPlaces,
      })}
      {suffix}
    </span>
  );
}
