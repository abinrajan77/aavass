"use client";

import { format } from "date-fns";
import { ColumnDef } from "@tanstack/react-table";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { DataTable } from "@/components/data-table/data-table";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { PaymentStatusBadge, type PaymentStatus } from "@/components/status-badge";
import { formatCurrency } from "@/lib/utils";
import { getSpecialCollection, listSpecialCollectionDues } from "@/lib/api/special-collections";
import type { DueStatus, SpecialCollectionDue } from "@/lib/api/types";

const DUE_STATUS_LABEL: Record<DueStatus, PaymentStatus> = {
  pending: "Pending",
  paid: "Paid",
  overdue: "Overdue",
};

/**
 * Collection detail — stat cards + dues table. Deliberately read-only: no
 * "Mark Paid" row action / "View Receipt" link. Both delegate to Module 3's
 * `record_payment()`/receipt flow (specs/04-special-collections-expenditure/
 * backend.md), and this frontend slice's backend counterpart does not
 * implement `POST .../dues/{due_id}/mark-paid` or
 * `GET .../dues/{due_id}/receipt` yet (Module 3 doesn't exist in this repo).
 * The status badge and fields below still render so the screen is useful
 * for read-only review; wiring the payment action is left for once Module 3
 * lands.
 */
export function CollectionDetailClient({ towerId, collectionId }: { towerId: string; collectionId: string }) {
  const collectionQuery = useQuery({
    queryKey: ["special-collection", towerId, collectionId],
    queryFn: () => getSpecialCollection(towerId, collectionId),
  });

  const duesQuery = useQuery({
    queryKey: ["special-collection-dues", towerId, collectionId],
    queryFn: () => listSpecialCollectionDues(towerId, collectionId, { page: 1, page_size: 100 }),
  });

  const collection = collectionQuery.data;
  const dues = duesQuery.data?.items ?? [];

  const columns: ColumnDef<SpecialCollectionDue>[] = [
    { accessorKey: "flat_number", header: "Flat" },
    { accessorKey: "owner_name", header: "Responsible Party" },
    { id: "amount", header: "Amount", cell: ({ row }) => formatCurrency(row.original.amount) },
    { id: "due_date", header: "Due Date", cell: ({ row }) => format(new Date(row.original.due_date), "PP") },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => <PaymentStatusBadge status={DUE_STATUS_LABEL[row.original.status]} />,
    },
  ];

  if (collectionQuery.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </div>
      </div>
    );
  }

  if (!collection) {
    return <p className="text-sm text-muted-foreground">Special collection not found.</p>;
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-foreground">{collection.title}</h1>
        {collection.description ? <p className="text-sm text-muted-foreground">{collection.description}</p> : null}
        <p className="text-sm text-muted-foreground">
          {formatCurrency(collection.total_amount)} total, split equally · due {format(new Date(collection.due_date), "PP")}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardDescription>Collected</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold text-success">
              ₹<NumberTicker value={collection.collected_amount} decimalPlaces={2} />
            </div>
            <p className="text-sm text-muted-foreground">{collection.paid_count} due(s) paid</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Pending</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold text-warning">{collection.pending_count}</div>
            <p className="text-sm text-muted-foreground">due(s) not yet paid</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Overdue</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold text-destructive">{collection.overdue_count}</div>
            <p className="text-sm text-muted-foreground">past the grace period</p>
          </CardContent>
        </Card>
      </div>

      {collection.skipped_flats.length > 0 ? (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>{collection.skipped_flats.length} flat(s) skipped</AlertTitle>
          <AlertDescription>
            No due was generated for: {collection.skipped_flats.map((f) => f.flat_number).join(", ")} (no active
            owner on record).
          </AlertDescription>
        </Alert>
      ) : null}

      <DataTable columns={columns} data={dues} isLoading={duesQuery.isLoading} emptyMessage="No dues generated." />
    </div>
  );
}
