"use client";

import { format } from "date-fns";
import type { DateRange } from "react-day-picker";
import { CalendarIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

/**
 * Range-mode counterpart to `DatePickerField` — used by the `/expenditures`
 * filter bar's date-range filter (frontend.md: "date range `Calendar` (range
 * mode)").
 */
export function DateRangePicker({
  value,
  onChange,
  placeholder = "Filter by date range",
}: {
  value?: DateRange;
  onChange: (range: DateRange | undefined) => void;
  placeholder?: string;
}) {
  const label =
    value?.from && value?.to
      ? `${format(value.from, "PP")} – ${format(value.to, "PP")}`
      : value?.from
        ? format(value.from, "PP")
        : placeholder;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          className={cn("justify-start text-left font-normal", !value?.from && "text-muted-foreground")}
        >
          <CalendarIcon className="mr-2 h-4 w-4" />
          {label}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar mode="range" selected={value} onSelect={onChange} defaultMonth={value?.from} numberOfMonths={2} />
      </PopoverContent>
    </Popover>
  );
}
