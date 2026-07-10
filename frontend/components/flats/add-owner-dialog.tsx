"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { z } from "zod";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DateField } from "./date-field";
import { ownerCreateSchema } from "@/lib/schemas/owner";
import { useAddFlatOwnerMutation } from "@/lib/hooks/use-flats";
import type { ApiError } from "@/lib/api/client";

const linkExistingSchema = z.object({
  owner_id: z.string().uuid("Enter a valid Owner id (UUID)"),
  is_primary_contact: z.boolean(),
  date_from: z.string().min(1, "Date is required"),
});
type LinkExistingInput = z.infer<typeof linkExistingSchema>;

/**
 * "Add Co-owner" dialog — frontend.md: "search existing global Owner by
 * phone/email or create new". backend.md's routes table doesn't document a
 * global owner-search endpoint (only `{owner_id, date_from,
 * is_primary_contact}` to *link* an existing Owner, or full `OwnerCreate` to
 * make a new one) — so "search by phone/email" isn't implementable against
 * the documented contract yet. This ships both documented paths: create a
 * new global Owner inline, or link an existing one by pasting its Owner id.
 * Flagging the missing search endpoint rather than inventing one.
 */
export function AddOwnerDialog({ towerId, flatId }: { towerId: string; flatId: string }) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"new" | "existing">("new");
  const addOwnerMutation = useAddFlatOwnerMutation(towerId, flatId);

  const newOwnerForm = useForm<z.infer<typeof ownerCreateSchema>>({
    resolver: zodResolver(ownerCreateSchema),
    defaultValues: {
      full_name: "",
      phone: "",
      email: "",
      id_number: "",
      is_primary_contact: false,
      date_from: "",
    },
  });

  const existingOwnerForm = useForm<LinkExistingInput>({
    resolver: zodResolver(linkExistingSchema),
    defaultValues: { owner_id: "", is_primary_contact: false, date_from: "" },
  });

  function close() {
    setOpen(false);
    newOwnerForm.reset();
    existingOwnerForm.reset();
    setMode("new");
  }

  function onError(err: unknown) {
    const apiErr = err as ApiError;
    toast.error(apiErr?.message ?? "Couldn't add owner");
  }

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? setOpen(true) : close())}>
      <DialogTrigger asChild>
        <Button size="sm">Add co-owner</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add co-owner</DialogTitle>
          <DialogDescription>Create a new owner record, or link an existing one by id.</DialogDescription>
        </DialogHeader>
        <Tabs value={mode} onValueChange={(v) => setMode(v as "new" | "existing")}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="new">New owner</TabsTrigger>
            <TabsTrigger value="existing">Existing owner id</TabsTrigger>
          </TabsList>
        </Tabs>

        {mode === "new" ? (
          <Form {...newOwnerForm}>
            <form
              className="space-y-4"
              onSubmit={newOwnerForm.handleSubmit((values) =>
                addOwnerMutation.mutate(
                  {
                    full_name: values.full_name,
                    phone: values.phone,
                    email: values.email || undefined,
                    id_number: values.id_number || undefined,
                    is_primary_contact: values.is_primary_contact,
                    date_from: values.date_from,
                  },
                  { onSuccess: () => { toast.success("Owner added"); close(); }, onError }
                )
              )}
            >
              <FormField
                control={newOwnerForm.control}
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
                control={newOwnerForm.control}
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
                control={newOwnerForm.control}
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
                control={newOwnerForm.control}
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
              <FormField
                control={newOwnerForm.control}
                name="date_from"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Ownership start date</FormLabel>
                    <DateField value={field.value} onChange={field.onChange} />
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={newOwnerForm.control}
                name="is_primary_contact"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-center gap-2 space-y-0">
                    <FormControl>
                      <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                    </FormControl>
                    <FormLabel className="font-normal">Make primary contact</FormLabel>
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="submit" disabled={addOwnerMutation.isPending}>
                  {addOwnerMutation.isPending ? "Adding..." : "Add owner"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        ) : (
          <Form {...existingOwnerForm}>
            <form
              className="space-y-4"
              onSubmit={existingOwnerForm.handleSubmit((values) =>
                addOwnerMutation.mutate(values, {
                  onSuccess: () => { toast.success("Owner linked"); close(); },
                  onError,
                })
              )}
            >
              <FormField
                control={existingOwnerForm.control}
                name="owner_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Owner id</FormLabel>
                    <FormControl>
                      <Input placeholder="00000000-0000-0000-0000-000000000000" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={existingOwnerForm.control}
                name="date_from"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Ownership start date</FormLabel>
                    <DateField value={field.value} onChange={field.onChange} />
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={existingOwnerForm.control}
                name="is_primary_contact"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-center gap-2 space-y-0">
                    <FormControl>
                      <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                    </FormControl>
                    <FormLabel className="font-normal">Make primary contact</FormLabel>
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="submit" disabled={addOwnerMutation.isPending}>
                  {addOwnerMutation.isPending ? "Linking..." : "Link owner"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        )}
      </DialogContent>
    </Dialog>
  );
}
