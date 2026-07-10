"use client";

import { format } from "date-fns";
import { CalendarIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

/**
 * Shared `Calendar` + `Popover` date-picker control — used by every Module 3
 * date field (formula `effective_from`, cycle `due_date`, mark-paid
 * `payment_date`) per specs/00-architecture-and-standards.md §3.2's
 * component palette. No prior date-picker exists elsewhere in the repo to
 * mirror, so this follows the standard shadcn.io "date picker" composition
 * of those two primitives, wired as a controlled `Date | undefined` field so
 * it drops straight into an RHF `FormField`'s `field.value`/`field.onChange`.
 */
export function DatePickerField({
  value,
  onChange,
  disabled,
  placeholder = "Pick a date",
  ariaLabel,
}: {
  value: Date | undefined;
  onChange: (date: Date | undefined) => void;
  disabled?: (date: Date) => boolean;
  placeholder?: string;
  /** Accessible name for the trigger button — the `<FormLabel>` sibling
   * this field renders alongside doesn't get wired to it via `htmlFor` the
   * way `<FormControl>` wires a plain input, since a `Popover` trigger
   * isn't a natural fit for that pattern; this keeps the button
   * screen-reader- and test-addressable regardless of its current date text. */
  ariaLabel?: string;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          aria-label={ariaLabel}
          className={cn("w-full justify-start text-left font-normal", !value && "text-muted-foreground")}
        >
          <CalendarIcon className="mr-2 h-4 w-4" />
          {value ? format(value, "PPP") : placeholder}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar mode="single" selected={value} onSelect={onChange} disabled={disabled} autoFocus />
      </PopoverContent>
    </Popover>
  );
}
