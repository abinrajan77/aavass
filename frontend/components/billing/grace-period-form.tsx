"use client";

import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { gracePeriodSchema, type GracePeriodInput } from "@/lib/schemas/billing";

export interface GracePeriodFormProps {
  defaultValues?: Partial<GracePeriodInput>;
  onSubmit: (values: GracePeriodInput) => void;
  isSubmitting?: boolean;
}

/**
 * Grace period config form — frontend.md §2.2. Single `grace_period_days`
 * field with inline helper text directly surfacing PRD §6.3.2's boundary
 * rule ("0 days means a due becomes Overdue the day after its due date")
 * so admins don't set 0 by accident (overview.md edge case 2).
 */
export function GracePeriodForm({ defaultValues, onSubmit, isSubmitting }: GracePeriodFormProps) {
  const form = useForm<GracePeriodInput>({
    // See formula-form.tsx for why this cast is needed (zod v4 `z.coerce` +
    // @hookform/resolvers v5 input/output typing friction, not a runtime issue).
    resolver: zodResolver(gracePeriodSchema) as Resolver<GracePeriodInput>,
    defaultValues: { grace_period_days: defaultValues?.grace_period_days ?? 0 },
  });

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="grace_period_days"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Grace period (days)</FormLabel>
              <FormControl>
                <Input type="number" step="1" min={0} {...field} />
              </FormControl>
              <FormDescription>
                0 days means a due becomes Overdue the day after its due date.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving..." : "Save grace period"}
        </Button>
      </form>
    </Form>
  );
}
