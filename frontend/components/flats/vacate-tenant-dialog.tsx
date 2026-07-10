"use client";

import { useForm } from "react-hook-form";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DateField } from "./date-field";
import { tenantVacateSchema, type TenantVacate } from "@/lib/schemas/tenant";
import { useVacateTenantMutation } from "@/lib/hooks/use-flats";
import type { ApiError } from "@/lib/api/client";
import type { Tenant } from "@/lib/api/types";

/**
 * Vacate dialog — frontend.md: "asking for vacated_date (Calendar) and a
 * required Select for the resulting occupancy_status (Owner-occupied /
 * Vacant) — the form cannot submit without this selection" (PRD §6.2.3).
 * The submit button is explicitly gated on `occupancy_status` being set (not
 * just on zod validity) so this exact behavior stays testable/obvious per
 * the frontend test plan's "vacate Dialog's submit button stays disabled
 * until occupancy_status is selected".
 */
export function VacateTenantDialog({
  towerId,
  flatId,
  tenant,
  open,
  onOpenChange,
}: {
  towerId: string;
  flatId: string;
  tenant: Tenant | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const vacateMutation = useVacateTenantMutation(towerId, flatId);
  const form = useForm<TenantVacate>({
    resolver: zodResolver(tenantVacateSchema),
    // occupancy_status is intentionally left unset (not defaulted) so the
    // submit button starts disabled — backend.md: "no default".
    defaultValues: { vacated_date: "", occupancy_status: undefined },
  });

  const occupancyStatus = form.watch("occupancy_status");
  const vacatedDate = form.watch("vacated_date");

  function close() {
    onOpenChange(false);
    form.reset({ vacated_date: "", occupancy_status: undefined });
  }

  if (!tenant) return null;

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? onOpenChange(true) : close())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Vacate {tenant.full_name}</DialogTitle>
          <DialogDescription>
            Specify the resulting occupancy status — it is never defaulted automatically.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            className="space-y-4"
            onSubmit={form.handleSubmit((values) =>
              vacateMutation.mutate(
                { tenantId: tenant.id, input: values },
                {
                  onSuccess: () => {
                    toast.success(`Tenant vacated — flat is now ${values.occupancy_status}`);
                    close();
                  },
                  onError: (err) => {
                    const apiErr = err as ApiError;
                    toast.error(apiErr?.message ?? "Couldn't vacate tenant");
                  },
                }
              )
            )}
          >
            <FormField
              control={form.control}
              name="vacated_date"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Vacated date</FormLabel>
                  <DateField value={field.value} onChange={field.onChange} />
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="occupancy_status"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Resulting occupancy status</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select occupancy status" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="owner_occupied">Owner-occupied</SelectItem>
                      <SelectItem value="vacant">Vacant</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={close}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={!occupancyStatus || !vacatedDate || vacateMutation.isPending}
              >
                {vacateMutation.isPending ? "Vacating..." : "Vacate tenant"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
