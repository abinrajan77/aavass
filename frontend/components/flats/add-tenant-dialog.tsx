"use client";

import { useState } from "react";
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
  DialogTrigger,
} from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { DateField } from "./date-field";
import { tenantCreateSchema, type TenantCreate } from "@/lib/schemas/tenant";
import { useCreateTenantMutation } from "@/lib/hooks/use-flats";
import type { ApiError } from "@/lib/api/client";

/**
 * "Add Tenant" dialog — frontend.md Tenants tab. Shown to both admins
 * (MANAGE_RESIDENTS) and flat owners (MANAGE_OWN_FLAT, own flat) per
 * backend.md's routes table — the caller decides which surface renders it.
 */
export function AddTenantDialog({ towerId, flatId }: { towerId: string; flatId: string }) {
  const [open, setOpen] = useState(false);
  const createTenantMutation = useCreateTenantMutation(towerId, flatId);

  const form = useForm<TenantCreate>({
    resolver: zodResolver(tenantCreateSchema),
    defaultValues: { full_name: "", phone: "", email: "", id_number: "", lease_start: "", lease_end: "" },
  });

  function close() {
    setOpen(false);
    form.reset();
  }

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? setOpen(true) : close())}>
      <DialogTrigger asChild>
        <Button>Add tenant</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add tenant</DialogTitle>
          <DialogDescription>
            The flat&apos;s occupancy status becomes Tenant-occupied on save.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            className="space-y-4"
            onSubmit={form.handleSubmit((values) =>
              createTenantMutation.mutate(
                {
                  full_name: values.full_name,
                  phone: values.phone,
                  email: values.email || undefined,
                  id_number: values.id_number || undefined,
                  lease_start: values.lease_start,
                  lease_end: values.lease_end || undefined,
                },
                {
                  onSuccess: () => {
                    toast.success("Tenant added — occupancy status updated");
                    close();
                  },
                  onError: (err) => {
                    const apiErr = err as ApiError;
                    toast.error(
                      apiErr?.errorCode === "ONE_ACTIVE_TENANT"
                        ? "This flat already has an active tenant — vacate them first."
                        : apiErr?.message ?? "Couldn't add tenant"
                    );
                  },
                }
              )
            )}
          >
            <FormField
              control={form.control}
              name="full_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Full name</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="phone"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Phone</FormLabel>
                  <FormControl>
                    <Input placeholder="9876543210" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email (optional)</FormLabel>
                  <FormControl>
                    <Input type="email" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="id_number"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>ID number (optional)</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="lease_start"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Lease start</FormLabel>
                    <DateField value={field.value} onChange={field.onChange} />
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="lease_end"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Lease end (optional)</FormLabel>
                    <DateField value={field.value} onChange={field.onChange} />
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <DialogFooter>
              <Button type="submit" disabled={createTenantMutation.isPending}>
                {createTenantMutation.isPending ? "Adding..." : "Add tenant"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
