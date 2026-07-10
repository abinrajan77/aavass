"use client";

import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DatePickerField } from "@/components/billing/date-picker-field";
import { markPaidSchema, type MarkPaidInput } from "@/lib/schemas/billing";
import { useMarkDuePaid } from "@/hooks/use-dues";
import { ApiError } from "@/lib/api/client";
import type { MaintenanceDue } from "@/lib/api/types";

const PAYMENT_MODE_LABELS: Record<MarkPaidInput["payment_mode"], string> = {
  cash: "Cash",
  bank_transfer: "Bank Transfer",
  cheque: "Cheque",
};

/**
 * Mark-paid dialog — frontend.md §2.4. Only rendered for Pending/Overdue
 * rows, gated by `<Can permission="RECORD_PAYMENT">` at the call site (the
 * dues table decides whether the row action is even shown).
 */
export function MarkPaidDialog({
  towerId,
  due,
  open,
  onOpenChange,
}: {
  towerId: string;
  due: MaintenanceDue;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const form = useForm<MarkPaidInput>({
    // See formula-form.tsx for why this cast is needed (zod v4 `z.coerce` +
    // @hookform/resolvers v5 input/output typing friction, not a runtime issue).
    resolver: zodResolver(markPaidSchema) as Resolver<MarkPaidInput>,
    defaultValues: {
      payment_date: new Date(),
      amount_received: due.amount,
      payment_mode: "cash",
      reference_number: "",
    },
  });

  const markPaidMutation = useMarkDuePaid(towerId);

  function handleSubmit(values: MarkPaidInput) {
    markPaidMutation.mutate(
      {
        dueId: due.id,
        payment_date: values.payment_date.toISOString().slice(0, 10),
        amount_received: values.amount_received,
        payment_mode: values.payment_mode,
        reference_number: values.reference_number || null,
      },
      {
        onSuccess: () => {
          toast.success("Payment recorded — receipt generated");
          onOpenChange(false);
          form.reset();
        },
        onError: (err) => {
          if (err instanceof ApiError && err.status === 409 && err.errorCode === "DUE_ALREADY_PAID") {
            // Double-click race — the row already reflects Paid via query invalidation.
            toast.error("This due was already marked as paid");
            onOpenChange(false);
            return;
          }
          toast.error("Couldn't record the payment");
        },
      }
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Mark due as paid</DialogTitle>
          <DialogDescription>
            Flat {due.flat_number} — ₹{due.amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="payment_date"
              render={({ field }) => (
                <FormItem className="flex flex-col">
                  <FormLabel>Payment date</FormLabel>
                  <DatePickerField
                    value={field.value}
                    onChange={field.onChange}
                    disabled={(date) => date > new Date()}
                    ariaLabel="Payment date"
                  />
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="amount_received"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Amount received (₹)</FormLabel>
                  <FormControl>
                    <Input type="number" step="0.01" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="payment_mode"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Payment mode</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select a payment mode" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {Object.entries(PAYMENT_MODE_LABELS).map(([value, label]) => (
                        <SelectItem key={value} value={value}>
                          {label}
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
              name="reference_number"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Reference number (optional)</FormLabel>
                  <FormControl>
                    <Input placeholder="Cheque/UTR number" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={markPaidMutation.isPending}>
                {markPaidMutation.isPending ? "Recording..." : "Mark as paid"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
