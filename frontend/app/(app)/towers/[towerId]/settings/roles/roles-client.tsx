"use client";

import { useState } from "react";
import { ColumnDef } from "@tanstack/react-table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { DataTable } from "@/components/data-table/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Can } from "@/components/auth/can";
import { PERMISSIONS, PERMISSION_CATALOG } from "@/lib/permissions";
import { createRoleSchema, type CreateRoleInput } from "@/lib/schemas/role";
import { createRole, listRoles } from "@/lib/api/roles";
import type { Role } from "@/lib/api/types";

export function RolesClient({ towerId }: { towerId: string }) {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);

  const rolesQuery = useQuery({
    queryKey: ["roles", towerId],
    queryFn: () => listRoles(towerId, { page: 1, page_size: 100 }),
  });

  const form = useForm<CreateRoleInput>({
    resolver: zodResolver(createRoleSchema),
    defaultValues: { name: "", permissionCodes: [] },
  });

  const removesRoleManagement =
    !form.watch("permissionCodes").includes(PERMISSIONS.MANAGE_ASSOCIATION_MEMBERS) &&
    form.watch("permissionCodes").length > 0;

  const createMutation = useMutation({
    mutationFn: (values: CreateRoleInput) =>
      createRole(towerId, { name: values.name, permission_codes: values.permissionCodes }),
    onSuccess: () => {
      toast.success("Role created");
      setCreateOpen(false);
      form.reset();
      queryClient.invalidateQueries({ queryKey: ["roles", towerId] });
    },
    onError: () => toast.error("Couldn't create role"),
  });

  const columns: ColumnDef<Role>[] = [
    {
      accessorKey: "name",
      header: "Role",
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <span>{row.original.name}</span>
          {row.original.is_system_default ? <Badge variant="mutedOutline">System default</Badge> : null}
        </div>
      ),
    },
    {
      id: "permissions",
      header: "Permissions",
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">
          {row.original.permission_codes.length} permission(s)
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Roles</h1>
          <p className="text-sm text-muted-foreground">
            The seeded Admin role has every permission and can&apos;t be edited or deactivated.
          </p>
        </div>
        <Can permission={PERMISSIONS.MANAGE_ASSOCIATION_MEMBERS}>
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button>Create role</Button>
            </DialogTrigger>
            <DialogContent className="max-h-[85vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Create custom role</DialogTitle>
                <DialogDescription>Pick exactly the permissions this role should have.</DialogDescription>
              </DialogHeader>
              <Form {...form}>
                <form onSubmit={form.handleSubmit((v) => createMutation.mutate(v))} className="space-y-4">
                  <FormField
                    control={form.control}
                    name="name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Role name</FormLabel>
                        <FormControl>
                          <Input placeholder="e.g. Secretary" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="permissionCodes"
                    render={() => (
                      <FormItem>
                        <FormLabel>Permissions</FormLabel>
                        <div className="grid gap-3 rounded-md border border-border p-3">
                          {PERMISSION_CATALOG.map((perm) => (
                            <FormField
                              key={perm.code}
                              control={form.control}
                              name="permissionCodes"
                              render={({ field }) => {
                                const checked = field.value?.includes(perm.code);
                                return (
                                  <FormItem className="flex flex-row items-start gap-3 space-y-0">
                                    <FormControl>
                                      <Checkbox
                                        checked={checked}
                                        onCheckedChange={(isChecked) => {
                                          const next = isChecked
                                            ? [...field.value, perm.code]
                                            : field.value.filter((c: string) => c !== perm.code);
                                          field.onChange(next);
                                        }}
                                      />
                                    </FormControl>
                                    <div className="space-y-0.5 leading-none">
                                      <FormLabel className="font-normal">{perm.code}</FormLabel>
                                      <p className="text-xs text-muted-foreground">{perm.description}</p>
                                    </div>
                                  </FormItem>
                                );
                              }}
                            />
                          ))}
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  {removesRoleManagement ? (
                    <Alert>
                      <AlertDescription>
                        This role doesn&apos;t include &quot;manage association members&quot; — if you
                        currently hold this exact role, this may remove your own ability to manage
                        roles. The Admin role always remains available as a recovery path.
                      </AlertDescription>
                    </Alert>
                  ) : null}
                  <DialogFooter>
                    <Button type="submit" disabled={createMutation.isPending}>
                      {createMutation.isPending ? "Creating..." : "Create role"}
                    </Button>
                  </DialogFooter>
                </form>
              </Form>
            </DialogContent>
          </Dialog>
        </Can>
      </div>

      <DataTable columns={columns} data={rolesQuery.data?.items ?? []} isLoading={rolesQuery.isLoading} />
    </div>
  );
}
