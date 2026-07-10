"use client";

import { useState } from "react";
import Link from "next/link";
import { ColumnDef } from "@tanstack/react-table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { ArrowRight } from "lucide-react";
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
import { createComplexSchema, type CreateComplexInput } from "@/lib/schemas/complex";
import { createComplex, listComplexes } from "@/lib/api/complexes";
import type { ApartmentComplex } from "@/lib/api/types";

export function ComplexesClient() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);

  const complexesQuery = useQuery({
    queryKey: ["complexes"],
    queryFn: () => listComplexes({ page: 1, page_size: 100 }),
  });

  const form = useForm<CreateComplexInput>({
    resolver: zodResolver(createComplexSchema),
    defaultValues: { name: "", address: "" },
  });

  const createMutation = useMutation({
    mutationFn: (values: CreateComplexInput) => createComplex(values),
    onSuccess: () => {
      toast.success("Complex created");
      setCreateOpen(false);
      form.reset();
      queryClient.invalidateQueries({ queryKey: ["complexes"] });
    },
    onError: () => toast.error("Couldn't create complex"),
  });

  const columns: ColumnDef<ApartmentComplex>[] = [
    { accessorKey: "name", header: "Name" },
    { accessorKey: "address", header: "Address" },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => <ActiveStateBadge deactivatedAt={row.original.deactivated_at} />,
    },
    {
      id: "towers",
      header: "",
      cell: ({ row }) => (
        <Link
          href={`/admin/complexes/${row.original.id}/towers`}
          className="flex items-center gap-1 text-sm text-primary hover:underline"
        >
          Towers <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Apartment complexes</h1>
          <p className="text-sm text-muted-foreground">Superuser only — create and manage complex records.</p>
        </div>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button>New complex</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create apartment complex</DialogTitle>
              <DialogDescription>You can add towers to it right after.</DialogDescription>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit((v) => createMutation.mutate(v))} className="space-y-4">
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
                  name="address"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Address</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <DialogFooter>
                  <Button type="submit" disabled={createMutation.isPending}>
                    {createMutation.isPending ? "Creating..." : "Create complex"}
                  </Button>
                </DialogFooter>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      <DataTable
        columns={columns}
        data={complexesQuery.data?.items ?? []}
        isLoading={complexesQuery.isLoading}
        emptyMessage="No complexes yet."
      />
    </div>
  );
}
