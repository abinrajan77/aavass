"use client";

import { useState } from "react";
import { ColumnDef } from "@tanstack/react-table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { DataTable } from "@/components/data-table/data-table";
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
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ActiveStateBadge } from "@/components/status-badge";
import { Can } from "@/components/auth/can";
import { PERMISSIONS } from "@/lib/permissions";
import { createAssociationMemberSchema, type CreateAssociationMemberInput } from "@/lib/schemas/association-member";
import {
  createAssociationMember,
  deactivateAssociationMember,
  listAssociationMembers,
} from "@/lib/api/association-members";
import { listRoles } from "@/lib/api/roles";
import type { AssociationMember } from "@/lib/api/types";

export function AssociationMembersClient({ towerId }: { towerId: string }) {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [detailMember, setDetailMember] = useState<AssociationMember | null>(null);

  const membersQuery = useQuery({
    queryKey: ["association-members", towerId],
    queryFn: () => listAssociationMembers(towerId, { page: 1, page_size: 100 }),
  });

  const rolesQuery = useQuery({
    queryKey: ["roles", towerId],
    queryFn: () => listRoles(towerId, { page: 1, page_size: 100 }),
  });

  const form = useForm<CreateAssociationMemberInput>({
    resolver: zodResolver(createAssociationMemberSchema),
    defaultValues: { name: "", email: "", phone: "", roleId: "" },
  });

  const createMutation = useMutation({
    mutationFn: (values: CreateAssociationMemberInput) =>
      createAssociationMember(towerId, {
        name: values.name,
        email: values.email,
        phone: values.phone,
        role_id: values.roleId,
      }),
    onSuccess: (res) => {
      toast.success(`Member added — temporary password: ${res.temporary_password}`);
      setCreateOpen(false);
      form.reset();
      queryClient.invalidateQueries({ queryKey: ["association-members", towerId] });
    },
    onError: () => toast.error("Couldn't add association member"),
  });

  const deactivateMutation = useMutation({
    mutationFn: (memberId: string) => deactivateAssociationMember(towerId, memberId),
    onSuccess: () => {
      toast.success("Member deactivated");
      setDetailMember(null);
      queryClient.invalidateQueries({ queryKey: ["association-members", towerId] });
    },
    onError: (err: unknown) => {
      const message =
        err && typeof err === "object" && "message" in err ? String((err as Error).message) : undefined;
      toast.error(message ?? "Couldn't deactivate member (may be the last Admin)");
    },
  });

  const columns: ColumnDef<AssociationMember>[] = [
    { accessorKey: "name", header: "Name" },
    { accessorKey: "email", header: "Email" },
    { accessorKey: "role_name", header: "Role" },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => <ActiveStateBadge deactivatedAt={row.original.deactivated_at} />,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Association members</h1>
          <p className="text-sm text-muted-foreground">Add, edit, or deactivate association members and their role.</p>
        </div>
        <Can permission={PERMISSIONS.MANAGE_ASSOCIATION_MEMBERS}>
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button>Add member</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add association member</DialogTitle>
                <DialogDescription>
                  A temporary password is generated and shown once — relay it manually.
                </DialogDescription>
              </DialogHeader>
              <Form {...form}>
                <form
                  onSubmit={form.handleSubmit((v) => createMutation.mutate(v))}
                  className="space-y-4"
                >
                  <FormField
                    control={form.control}
                    name="name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Name</FormLabel>
                        <FormControl>
                          <Input {...field} />
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
                        <FormLabel>Email</FormLabel>
                        <FormControl>
                          <Input type="email" {...field} />
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
                    name="roleId"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Role</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="Select a role" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {rolesQuery.data?.items.map((role) => (
                              <SelectItem key={role.id} value={role.id}>
                                {role.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <DialogFooter>
                    <Button type="submit" disabled={createMutation.isPending}>
                      {createMutation.isPending ? "Adding..." : "Add member"}
                    </Button>
                  </DialogFooter>
                </form>
              </Form>
            </DialogContent>
          </Dialog>
        </Can>
      </div>

      <DataTable
        columns={columns}
        data={membersQuery.data?.items ?? []}
        isLoading={membersQuery.isLoading}
        onRowClick={(member) => setDetailMember(member)}
        emptyMessage="No association members yet."
      />

      <Sheet open={!!detailMember} onOpenChange={(open) => !open && setDetailMember(null)}>
        <SheetContent>
          {detailMember ? (
            <>
              <SheetHeader>
                <SheetTitle>{detailMember.name}</SheetTitle>
                <SheetDescription>{detailMember.email}</SheetDescription>
              </SheetHeader>
              <div className="mt-6 space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Phone</span>
                  <span>{detailMember.phone}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Role</span>
                  <span>{detailMember.role_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Status</span>
                  <ActiveStateBadge deactivatedAt={detailMember.deactivated_at} />
                </div>
              </div>
              <Can permission={PERMISSIONS.MANAGE_ASSOCIATION_MEMBERS}>
                {!detailMember.deactivated_at && (
                  <Button
                    variant="outline"
                    className="mt-6 w-full text-destructive hover:text-destructive"
                    onClick={() => deactivateMutation.mutate(detailMember.id)}
                    disabled={deactivateMutation.isPending}
                  >
                    Deactivate member
                  </Button>
                )}
              </Can>
            </>
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}
