"use client";

import { useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ColumnDef } from "@tanstack/react-table";
import { toast } from "sonner";
import { DataTable } from "@/components/data-table/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Can } from "@/components/auth/can";
import { PaymentStatusBadge, type PaymentStatus } from "@/components/status-badge";
import { PERMISSIONS } from "@/lib/permissions";
import { MarkPaidDialog } from "@/components/billing/mark-paid-dialog";
import { getDueReceipt } from "@/lib/api/billing";
import type { MaintenanceDue, MaintenanceDueStatus, Paginated } from "@/lib/api/types";

function dueStatusToPaymentStatus(status: MaintenanceDueStatus): PaymentStatus {
  if (status === "paid") return "Paid";
  if (status === "overdue") return "Overdue";
  return "Pending";
}

export interface DuesDataTableProps {
  towerId: string;
  /** Tabs to render — deliberately configurable per caller: the cycle-detail
   * page supports All/Pending/Paid/Overdue (backend.md §6.4's cycle-scoped
   * route documents all three statuses), while the cross-cycle /dues page
   * only supports All/Pending/Overdue (backend.md §6.4's cross-cycle route
   * documents `status=pending|overdue` only — see hooks/use-dues.ts). */
  statusOptions: { value: string; label: string }[];
  /**
   * Already-fetched data for the *current* `?status=` tab — the parent page
   * owns the actual `useCycleDues`/`useTowerDues` query call (each hits a
   * different API shape) and re-derives `status` from the same
   * `useSearchParams()` this component reads, per Rules of Hooks: a hook
   * can't safely be handed to a child as a plain function prop and invoked
   * conditionally from there, so query ownership stays with the page and
   * only the fetched result flows down.
   */
  dues?: Paginated<MaintenanceDue>;
  isLoading: boolean;
}

/**
 * Shared dues list — frontend.md §2.4 (cycle detail) / §2.5 (cross-cycle).
 * Status `Tabs` state is deep-linkable via `?status=`, per the component
 * test plan §4.1: "Status Tabs correctly reflect the ?status= query param on
 * direct navigation."
 */
export function DuesDataTable({ towerId, statusOptions, dues, isLoading }: DuesDataTableProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const activeStatus = searchParams.get("status") ?? "all";
  const [markPaidDue, setMarkPaidDue] = useState<MaintenanceDue | null>(null);

  function handleStatusChange(value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value === "all") {
      params.delete("status");
    } else {
      params.set("status", value);
    }
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname);
  }

  async function handleDownloadReceipt(due: MaintenanceDue) {
    try {
      const receipt = await getDueReceipt(towerId, due.id);
      window.open(receipt.download_url, "_blank");
    } catch {
      toast.error("Couldn't fetch the receipt");
    }
  }

  const columns: ColumnDef<MaintenanceDue>[] = [
    { accessorKey: "flat_number", header: "Flat Number" },
    {
      id: "assigned_to",
      header: "Assigned To",
      cell: ({ row }) => (
        <span className="inline-flex items-center gap-2">
          {row.original.assigned_to_name_snapshot}
          <Badge variant="mutedOutline" className="capitalize">
            {row.original.assigned_to_type}
          </Badge>
        </span>
      ),
    },
    {
      accessorKey: "amount",
      header: "Amount",
      cell: ({ row }) => `₹${row.original.amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`,
    },
    { accessorKey: "due_date", header: "Due Date" },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => <PaymentStatusBadge status={dueStatusToPaymentStatus(row.original.status)} />,
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => {
        const due = row.original;
        return (
          <div className="flex justify-end gap-2">
            {(due.status === "pending" || due.status === "overdue") && (
              <Can permission={PERMISSIONS.RECORD_PAYMENT}>
                <Button size="sm" variant="outline" onClick={() => setMarkPaidDue(due)}>
                  Mark Paid
                </Button>
              </Can>
            )}
            {due.status === "paid" && (
              <Button size="sm" variant="ghost" onClick={() => handleDownloadReceipt(due)}>
                Download Receipt
              </Button>
            )}
          </div>
        );
      },
    },
  ];

  return (
    <div className="space-y-4">
      <Tabs value={activeStatus} onValueChange={handleStatusChange}>
        <TabsList>
          {statusOptions.map((opt) => (
            <TabsTrigger key={opt.value} value={opt.value}>
              {opt.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <DataTable
        columns={columns}
        data={dues?.items ?? []}
        isLoading={isLoading}
        emptyMessage="No dues found."
      />

      {markPaidDue ? (
        <MarkPaidDialog
          towerId={towerId}
          due={markPaidDue}
          open={!!markPaidDue}
          onOpenChange={(open) => !open && setMarkPaidDue(null)}
        />
      ) : null}
    </div>
  );
}
