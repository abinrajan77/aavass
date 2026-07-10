"use client";

import { format } from "date-fns";
import { CalendarIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

/**
 * Shared `Calendar` + `Popover` single-date picker trigger, per
 * specs/00-architecture-and-standards.md §3.2 ("Calendar + Popover — date
 * pickers for due dates, lease dates"). Module 1's frontend had no date
 * fields, so this is the first date-picker pattern in the repo — extracted
 * here (rather than inlined per form) since Module 4 needs it in two places
 * (special collection due date, expenditure date).
 */
export function DatePickerField({
  value,
  onChange,
  placeholder = "Pick a date",
  disabledDate,
  id,
}: {
  value?: Date;
  onChange: (date: Date | undefined) => void;
  placeholder?: string;
  disabledDate?: (date: Date) => boolean;
  id?: string;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          className={cn("w-full justify-start text-left font-normal", !value && "text-muted-foreground")}
        >
          <CalendarIcon className="mr-2 h-4 w-4" />
          {value ? format(value, "PPP") : placeholder}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={value}
          onSelect={onChange}
          disabled={disabledDate}
          defaultMonth={value}
        />
      </PopoverContent>
    </Popover>
  );
}
