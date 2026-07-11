"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { format } from "date-fns";
import { ColumnDef } from "@tanstack/react-table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { DataTable } from "@/components/data-table/data-table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ShineBorder } from "@/components/magicui/shine-border";
import { Can } from "@/components/auth/can";
import { PERMISSIONS } from "@/lib/permissions";
import { formatCurrency } from "@/lib/utils";
import { createSpecialCollection, listSpecialCollections } from "@/lib/api/special-collections";
import { getActiveFlatCount } from "@/lib/api/flats";
import { getTower } from "@/lib/api/towers";
import type { SpecialCollection } from "@/lib/api/types";
import type { SpecialCollectionInput } from "@/lib/schemas/special-collection";
import { SpecialCollectionForm } from "./special-collection-form";

function CollectionProgress({ collected, total }: { collected: number; total: number }) {
  const pct = total > 0 ? Math.min(100, Math.round((collected / total) * 100)) : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-24 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-success" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-muted-foreground">{pct}%</span>
    </div>
  );
}

function CollectionStatusBadge({ collection }: { collection: SpecialCollection }) {
  const openCount = collection.pending_count + collection.overdue_count;
  if (openCount === 0) {
    return <Badge variant="success">Fully collected</Badge>;
  }
  return <Badge variant="outline">Open</Badge>;
}

export function SpecialCollectionsClient({ towerId }: { towerId: string }) {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);

  const collectionsQuery = useQuery({
    queryKey: ["special-collections", towerId],
    queryFn: () => listSpecialCollections(towerId, { page: 1, page_size: 100 }),
  });

  // Active-flat count for the live per-flat split preview (frontend.md) —
  // Module 2 isn't built yet in this repo, so this query is expected to 404
  // until it ships; the tower's configured `total_flats` is used as a
  // labeled fallback so the dialog still shows a useful estimate.
  const activeFlatCountQuery = useQuery({
    queryKey: ["active-flat-count", towerId],
    queryFn: () => getActiveFlatCount(towerId),
    enabled: createOpen,
    retry: false,
  });
  const towerQuery = useQuery({
    queryKey: ["tower", towerId],
    queryFn: () => getTower(towerId),
    enabled: createOpen,
  });

  const activeFlatCount = activeFlatCountQuery.data?.count ?? towerQuery.data?.total_flats ?? 0;
  const activeFlatCountIsFallback = !activeFlatCountQuery.data && !!towerQuery.data;

  const createMutation = useMutation({
    mutationFn: (values: SpecialCollectionInput) =>
      createSpecialCollection(towerId, {
        title: values.title,
        description: values.description || null,
        total_amount: values.total_amount,
        split_basis: values.split_basis,
        due_date: format(values.due_date, "yyyy-MM-dd"),
      }),
    onSuccess: (res) => {
      if (res.dues_generated) {
        toast.success("Special collection created");
      } else {
        toast.info("Large tower — dues are being generated in the background.");
      }
      if (res.skipped_flats.length > 0) {
        toast.warning(
          `Skipped ${res.skipped_flats.length} flat${res.skipped_flats.length === 1 ? "" : "s"} with no active owner: ${res.skipped_flats
            .map((f) => f.flat_number)
            .join(", ")}`
        );
      }
      setCreateOpen(false);
      queryClient.invalidateQueries({ queryKey: ["special-collections", towerId] });
    },
    onError: () => toast.error("Couldn't create special collection"),
  });

  const collections = useMemo(() => collectionsQuery.data?.items ?? [], [collectionsQuery.data]);

  const openCollections = useMemo(
    () => collections.filter((c) => c.pending_count + c.overdue_count > 0),
    [collections]
  );
  const outstandingAmount = useMemo(
    () => openCollections.reduce((sum, c) => sum + (c.total_amount - c.collected_amount), 0),
    [openCollections]
  );

  const columns: ColumnDef<SpecialCollection>[] = [
    {
      accessorKey: "title",
      header: "Title",
      cell: ({ row }) => (
        <Link
          href={`/towers/${towerId}/special-collections/${row.original.id}`}
          className="font-medium text-primary hover:underline"
        >
          {row.original.title}
        </Link>
      ),
    },
    {
      id: "total_amount",
      header: "Total Amount",
      cell: ({ row }) => formatCurrency(row.original.total_amount),
    },
    {
      id: "due_date",
      header: "Due Date",
      cell: ({ row }) => format(new Date(row.original.due_date), "PP"),
    },
    {
      id: "collected",
      header: "Collected",
      cell: ({ row }) => <CollectionProgress collected={row.original.collected_amount} total={row.original.total_amount} />,
    },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => <CollectionStatusBadge collection={row.original} />,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Special collections</h1>
          <p className="text-sm text-muted-foreground">One-off collections split equally across active flats.</p>
        </div>
        <Can permission={PERMISSIONS.MANAGE_SPECIAL_COLLECTIONS}>
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button>New special collection</Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle>Create special collection</DialogTitle>
                <DialogDescription>
                  Dues are generated immediately for every active flat with an active owner.
                </DialogDescription>
              </DialogHeader>
              <SpecialCollectionForm
                activeFlatCount={activeFlatCount}
                activeFlatCountIsFallback={activeFlatCountIsFallback}
                isSubmitting={createMutation.isPending}
                onCancel={() => setCreateOpen(false)}
                onSubmit={(values) => createMutation.mutate(values)}
              />
            </DialogContent>
          </Dialog>
        </Can>
      </div>

      <Card className="relative overflow-hidden border-accent/40">
        <ShineBorder />
        <CardHeader>
          <CardTitle>Open Special Collections</CardTitle>
          <CardDescription>Collections still awaiting full payment from at least one flat</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-baseline gap-8">
          <div>
            <div className="text-3xl font-semibold text-foreground">{openCollections.length}</div>
            <div className="text-sm text-muted-foreground">
              open collection{openCollections.length === 1 ? "" : "s"}
            </div>
          </div>
          <div>
            <div className="text-3xl font-semibold text-warning">{formatCurrency(outstandingAmount)}</div>
            <div className="text-sm text-muted-foreground">outstanding</div>
          </div>
        </CardContent>
      </Card>

      <DataTable
        columns={columns}
        data={collections}
        isLoading={collectionsQuery.isLoading}
        emptyMessage="No special collections yet."
      />
    </div>
  );
}
