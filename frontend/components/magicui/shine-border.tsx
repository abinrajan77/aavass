"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Minimal reimplementation of magicui's `ShineBorder` (magicui.design). The
 * `magicui` package isn't vendored as an npm dependency in this repo — each
 * module hand-rolls the small subset of magicui components it actually uses,
 * matching how components/ui/* hand-rolls shadcn primitives rather than
 * installing shadcn as a package. Used exactly once in this module, per
 * specs/00-architecture-and-standards.md §3.2 ("ShineBorder — highlight the
 * 'action needed' card") and specs/04-special-collections-expenditure/
 * frontend.md's magicui section: the "Open Special Collections" summary
 * card on `/special-collections`.
 *
 * Usage: render as an absolutely-positioned child of a `position: relative`
 * (or Tailwind `relative`) card with `overflow-hidden`.
 */
export function ShineBorder({
  className,
  borderWidth = 1,
  duration = 8,
  colors = ["hsl(var(--accent))", "hsl(var(--primary))"],
}: {
  className?: string;
  borderWidth?: number;
  duration?: number;
  colors?: string[];
}) {
  return (
    <div
      aria-hidden="true"
      data-testid="shine-border"
      className={cn("pointer-events-none absolute inset-0 rounded-[inherit]", className)}
      style={
        {
          backgroundImage: `radial-gradient(transparent, transparent, ${colors.join(", ")}, transparent, transparent)`,
          backgroundSize: "300% 300%",
          WebkitMask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
          WebkitMaskComposite: "xor",
          maskComposite: "exclude",
          padding: `${borderWidth}px`,
          animation: `shine ${duration}s linear infinite`,
        } as React.CSSProperties
      }
    />
  );
}
