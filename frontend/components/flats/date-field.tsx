"use client";

import { format } from "date-fns";
import { CalendarIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

/**
 * Shared Calendar+Popover date field (specs/00-architecture-and-standards.md
 * §3.2) — used across this module for lease_start/lease_end, vacated_date,
 * and ownership date_from. Stores/emits plain `yyyy-MM-dd` strings so it
 * plugs directly into the zod schemas mirroring backend.md's `date` fields.
 */
export function DateField({
  value,
  onChange,
  placeholder = "Pick a date",
  disabled,
  disabledDate,
}: {
  value?: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  disabledDate?: (date: Date) => boolean;
}) {
  const selected = value ? new Date(`${value}T00:00:00`) : undefined;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          disabled={disabled}
          className={cn("w-full justify-start text-left font-normal", !value && "text-muted-foreground")}
        >
          <CalendarIcon className="mr-2 h-4 w-4" />
          {selected ? format(selected, "PPP") : placeholder}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0">
        <Calendar
          mode="single"
          selected={selected}
          onSelect={(date) => date && onChange(format(date, "yyyy-MM-dd"))}
          disabled={disabledDate}
        />
      </PopoverContent>
    </Popover>
  );
}
