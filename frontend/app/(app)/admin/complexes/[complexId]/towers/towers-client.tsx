"use client";

import { useState } from "react";
import Link from "next/link";
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
import { ActiveStateBadge } from "@/components/status-badge";
import { createTowerSchema, type CreateTowerInput } from "@/lib/schemas/tower";
import { createTower, listTowersForComplex } from "@/lib/api/complexes";
import type { Tower } from "@/lib/api/types";

export function TowersClient({ complexId }: { complexId: string }) {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);

  const towersQuery = useQuery({
    queryKey: ["towers", complexId],
    queryFn: () => listTowersForComplex(complexId, { page: 1, page_size: 100 }),
  });

  const form = useForm<CreateTowerInput>({
    resolver: zodResolver(createTowerSchema),
    defaultValues: { name: "", code: "", totalFloors: 1, totalFlats: 1, associationName: "" },
  });

  const createMutation = useMutation({
    mutationFn: (values: CreateTowerInput) =>
      createTower(complexId, {
        name: values.name,
        code: values.code,
        total_floors: values.totalFloors,
        total_flats: values.totalFlats,
        association_name: values.associationName,
      }),
    onSuccess: () => {
      toast.success("Tower created — Admin role seeded with all permissions");
      setCreateOpen(false);
      form.reset();
      queryClient.invalidateQueries({ queryKey: ["towers", complexId] });
    },
    onError: () => toast.error("Couldn't create tower"),
  });

  const columns: ColumnDef<Tower>[] = [
    {
      accessorKey: "name",
      header: "Tower",
      cell: ({ row }) => (
        <Link href={`/towers/${row.original.id}`} className="text-primary hover:underline">
          {row.original.name}
        </Link>
      ),
    },
    { accessorKey: "code", header: "Code" },
    { accessorKey: "total_floors", header: "Floors" },
    { accessorKey: "total_flats", header: "Flats" },
    { accessorKey: "association_name", header: "Association" },
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
          <h1 className="text-lg font-semibold text-foreground">Towers</h1>
          <p className="text-sm text-muted-foreground">
            Creating a tower seeds its Admin role with every permission, per specs/01.
          </p>
        </div>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button>New tower</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create tower</DialogTitle>
              <DialogDescription>
                Code is short and uppercase — used in receipt numbering by Module 3.
              </DialogDescription>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit((v) => createMutation.mutate(v))} className="space-y-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Tower name</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="code"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Code</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="OAK"
                          {...field}
                          onChange={(e) => field.onChange(e.target.value.toUpperCase())}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="grid grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="totalFloors"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Total floors</FormLabel>
                        <FormControl>
                          <Input
                            type="number"
                            {...field}
                            onChange={(e) => field.onChange(Number(e.target.value))}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="totalFlats"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Total flats</FormLabel>
                        <FormControl>
                          <Input
                            type="number"
                            {...field}
                            onChange={(e) => field.onChange(Number(e.target.value))}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <FormField
                  control={form.control}
                  name="associationName"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Association name</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <DialogFooter>
                  <Button type="submit" disabled={createMutation.isPending}>
                    {createMutation.isPending ? "Creating..." : "Create tower"}
                  </Button>
                </DialogFooter>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      <DataTable
        columns={columns}
        data={towersQuery.data?.items ?? []}
        isLoading={towersQuery.isLoading}
        emptyMessage="No towers yet."
      />
    </div>
  );
}
