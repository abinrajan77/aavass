"use client";

import { useState } from "react";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { DatePickerField } from "@/components/billing/date-picker-field";
import { billingCycleSchema, type BillingCycleInput } from "@/lib/schemas/billing";
import { useCreateBillingCycle } from "@/hooks/use-billing-cycles";
import { useJobStatus } from "@/hooks/use-job-status";
import { ApiError } from "@/lib/api/client";
import type { BillingCycleJobAccepted } from "@/lib/api/types";

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/**
 * "Generate Cycle" dialog — frontend.md §2.3. Handles both the `201` sync
 * path (<=300 active flats, cycle created + active immediately) and the
 * `202` async path (job enqueued, polls the shared canonical
 * `GET /jobs/{job_id}` route every 2s until `done`), plus the
 * `409 BILLING_CYCLE_ALREADY_EXISTS` inline-error path.
 */
export function GenerateCycleDialog({ towerId }: { towerId: string }) {
  const [open, setOpen] = useState(false);
  const [jobAccepted, setJobAccepted] = useState<BillingCycleJobAccepted | null>(null);
  const queryClient = useQueryClient();

  const form = useForm<BillingCycleInput>({
    // See formula-form.tsx for why this cast is needed (zod v4 `z.coerce` +
    // @hookform/resolvers v5 input/output typing friction, not a runtime issue).
    resolver: zodResolver(billingCycleSchema) as Resolver<BillingCycleInput>,
    defaultValues: { month: new Date().getMonth() + 1, year: new Date().getFullYear() },
  });

  const createMutation = useCreateBillingCycle(towerId);

  useJobStatus(towerId, jobAccepted?.job_id ?? null, {
    enabled: !!jobAccepted,
    onDone: () => {
      toast.success("Billing cycle generated");
      // The 202-path invalidation in useCreateBillingCycle's onSuccess only
      // refreshes the list into its "generating" row — this second
      // invalidation, once the polled job actually finishes, is what makes
      // that row flip to "active" with its real due counts without a
      // manual page reload.
      queryClient.invalidateQueries({ queryKey: ["billing-cycles", towerId] });
      resetAndClose();
    },
    onFailed: () => {
      toast.error("Billing-cycle generation failed — check the tower's flat data and try again");
      queryClient.invalidateQueries({ queryKey: ["billing-cycles", towerId] });
      resetAndClose();
    },
  });

  function resetAndClose() {
    setJobAccepted(null);
    setOpen(false);
    form.reset({ month: new Date().getMonth() + 1, year: new Date().getFullYear() });
  }

  async function handleSubmit(values: BillingCycleInput) {
    try {
      const result = await createMutation.mutateAsync({
        month: values.month,
        year: values.year,
        due_date: values.due_date.toISOString().slice(0, 10),
      });

      if (result.status === 201) {
        toast.success("Billing cycle generated");
        resetAndClose();
      } else {
        // 202 — async job enqueued, switch this dialog into the polling/progress state.
        setJobAccepted(result.data as BillingCycleJobAccepted);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 409 && err.errorCode === "BILLING_CYCLE_ALREADY_EXISTS") {
        // Inline form error, not a toast — this is a correctable input error.
        form.setError("month", { message: "A billing cycle for this month/year already exists." });
        return;
      }
      toast.error("Couldn't generate the billing cycle");
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && jobAccepted) return; // don't allow closing mid-generation
        setOpen(next);
      }}
    >
      <DialogTrigger asChild>
        <Button>Generate Cycle</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Generate billing cycle</DialogTitle>
          <DialogDescription>
            Creates one due per active flat, using the formula and grace period currently in effect.
          </DialogDescription>
        </DialogHeader>

        {jobAccepted ? (
          <div className="space-y-3 py-2">
            <Skeleton className="h-4 w-3/4" />
            <p className="text-sm text-muted-foreground">
              Generating dues for this cycle — this may take a minute. This dialog will close automatically
              when it&apos;s done.
            </p>
          </div>
        ) : (
          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="month"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Month</FormLabel>
                      <Select onValueChange={(v) => field.onChange(Number(v))} value={String(field.value)}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select a month" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {MONTH_NAMES.map((name, idx) => (
                            <SelectItem key={name} value={String(idx + 1)}>
                              {name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="year"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Year</FormLabel>
                      <FormControl>
                        <Input type="number" {...field} onChange={(e) => field.onChange(Number(e.target.value))} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={form.control}
                name="due_date"
                render={({ field }) => (
                  <FormItem className="flex flex-col">
                    <FormLabel>Due date</FormLabel>
                    <DatePickerField value={field.value} onChange={field.onChange} ariaLabel="Due date" />
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending ? "Generating..." : "Generate"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        )}
      </DialogContent>
    </Dialog>
  );
}
