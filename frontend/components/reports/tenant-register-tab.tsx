"use client";

import { useMemo } from "react";
import { ColumnDef } from "@tanstack/react-table";
import { format } from "date-fns";
import { DataTable } from "@/components/data-table/data-table";
import { Badge } from "@/components/ui/badge";
import { ExportButtons } from "./export-buttons";
import { ReportEmptyState } from "./report-empty-state";
import { useTenantRegisterReport } from "@/hooks/use-reports";
import type { TenantRegisterRow } from "@/lib/api/types";

/**
 * Tenant Register — specs/05-reporting-owner-portal-notifications/
 * frontend.md §2: "no period control (point-in-time register)."
 */
export function TenantRegisterTab({ towerId }: { towerId: string }) {
  const reportQuery = useTenantRegisterReport(towerId);
  const items = reportQuery.data?.items ?? [];

  const columns: ColumnDef<TenantRegisterRow>[] = useMemo(
    () => [
      { accessorKey: "flat_number", header: "Flat" },
      { accessorKey: "tenant_name", header: "Tenant" },
      { accessorKey: "phone_number", header: "Phone" },
      { id: "email", header: "Email", cell: ({ row }) => row.original.email ?? "—" },
      {
        id: "lease_start",
        header: "Lease Start",
        cell: ({ row }) => format(new Date(row.original.lease_start), "PP"),
      },
      {
        id: "lease_end",
        header: "Lease End",
        cell: ({ row }) => (row.original.lease_end ? format(new Date(row.original.lease_end), "PP") : "—"),
      },
      {
        id: "is_current",
        header: "Status",
        cell: ({ row }) =>
          row.original.is_current ? (
            <Badge variant="accent">Current</Badge>
          ) : (
            <Badge variant="mutedOutline">Past</Badge>
          ),
      },
    ],
    []
  );

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <ExportButtons towerId={towerId} reportType="tenant_register" params={{}} />
      </div>
      {reportQuery.data && items.length === 0 ? (
        <ReportEmptyState message="No tenants recorded for this tower." />
      ) : (
        <DataTable
          columns={columns}
          data={items}
          isLoading={reportQuery.isLoading}
          emptyMessage="No tenants recorded for this tower."
        />
      )}
    </div>
  );
}
