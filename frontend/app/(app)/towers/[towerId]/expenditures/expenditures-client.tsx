"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { format } from "date-fns";
import type { DateRange } from "react-day-picker";
import { ColumnDef } from "@tanstack/react-table";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Paperclip } from "lucide-react";
import { DataTable } from "@/components/data-table/data-table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DateRangePicker } from "@/components/form/date-range-picker";
import { Can } from "@/components/auth/can";
import { PERMISSIONS } from "@/lib/permissions";
import { formatCurrency } from "@/lib/utils";
import { getExpenditureAttachmentUrl, listExpenditures } from "@/lib/api/expenditures";
import type { Expenditure, ExpenditureCategory } from "@/lib/api/types";

const CATEGORY_LABEL: Record<ExpenditureCategory, string> = {
  cleaning: "Cleaning",
  security: "Security",
  repairs: "Repairs",
  utilities: "Utilities",
  other: "Other",
};

function AttachmentLink({ towerId, expenditure }: { towerId: string; expenditure: Expenditure }) {
  if (!expenditure.attachment_s3_key) return <span className="text-muted-foreground">—</span>;

  return (
    <button
      type="button"
      aria-label="View attachment"
      className="inline-flex items-center text-primary hover:underline"
      onClick={async () => {
        try {
          const { url } = await getExpenditureAttachmentUrl(towerId, expenditure.id);
          window.open(url, "_blank", "noopener,noreferrer");
        } catch {
          toast.error("Couldn't open attachment");
        }
      }}
    >
      <Paperclip className="h-4 w-4" />
    </button>
  );
}

export function ExpendituresClient({ towerId }: { towerId: string }) {
  const [category, setCategory] = useState<ExpenditureCategory | "all">("all");
  const [complexOnly, setComplexOnly] = useState(false);
  const [dateRange, setDateRange] = useState<DateRange | undefined>(undefined);

  const expendituresQuery = useQuery({
    queryKey: ["expenditures", towerId, category, complexOnly, dateRange?.from, dateRange?.to],
    queryFn: () =>
      listExpenditures(towerId, {
        page: 1,
        page_size: 100,
        category: category === "all" ? undefined : category,
        is_complex_contribution: complexOnly ? true : undefined,
        date_from: dateRange?.from ? format(dateRange.from, "yyyy-MM-dd") : undefined,
        date_to: dateRange?.to ? format(dateRange.to, "yyyy-MM-dd") : undefined,
      }),
  });

  const expenditures = useMemo(() => expendituresQuery.data?.items ?? [], [expendituresQuery.data]);

  // Client-side category totals over the current (filtered) page — a full
  // tower-wide report is Module 5's responsibility
  // (specs/00-architecture-and-standards.md §2); this is just a quick-glance
  // strip on the working list screen. Per backend.md's design decision,
  // `complex_total_amount` never contributes to a sum — only `amount` (the
  // tower's own posted share) does.
  const categoryTotals = useMemo(() => {
    const totals = new Map<ExpenditureCategory, number>();
    for (const e of expenditures) {
      // `amount` is typed `number` but the backend serializes Decimal fields as JSON
      // strings (e.g. "10982.00") — `+` on two strings concatenates rather than adds,
      // which only broke visibly once a category had 2+ entries (a single string still
      // coerces fine via Intl.NumberFormat, but concatenating two decimal strings
      // produces an invalid multi-"." literal that parses to NaN). `Number(...)` is a
      // harmless no-op when the value is already numeric.
      totals.set(e.category, (totals.get(e.category) ?? 0) + Number(e.amount));
    }
    return totals;
  }, [expenditures]);

  const columns: ColumnDef<Expenditure>[] = [
    { id: "date", header: "Date", cell: ({ row }) => format(new Date(row.original.expenditure_date), "PP") },
    {
      id: "category",
      header: "Category",
      cell: ({ row }) => <Badge variant="secondary">{CATEGORY_LABEL[row.original.category]}</Badge>,
    },
    { accessorKey: "description", header: "Description" },
    { accessorKey: "vendor_payee_name", header: "Vendor/Payee" },
    { id: "amount", header: "Amount", cell: ({ row }) => formatCurrency(row.original.amount) },
    {
      id: "attachment",
      header: "Attachment",
      cell: ({ row }) => <AttachmentLink towerId={towerId} expenditure={row.original} />,
    },
    {
      id: "complex_contribution",
      header: "Complex Contribution",
      cell: ({ row }) =>
        row.original.is_complex_contribution ? <Badge variant="outline">Complex</Badge> : null,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Expenditures</h1>
          <p className="text-sm text-muted-foreground">Tower expenses, including this tower&apos;s share of complex-wide costs.</p>
        </div>
        <Can permission={PERMISSIONS.MANAGE_EXPENDITURE}>
          <div className="flex gap-2">
            <Button variant="outline" asChild>
              <Link href={`/towers/${towerId}/expenditures/new?type=complex-contribution`}>
                New complex contribution
              </Link>
            </Button>
            <Button asChild>
              <Link href={`/towers/${towerId}/expenditures/new`}>New expenditure</Link>
            </Button>
          </div>
        </Can>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <Select value={category} onValueChange={(v) => setCategory(v as ExpenditureCategory | "all")}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="All categories" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All categories</SelectItem>
            {Object.entries(CATEGORY_LABEL).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <DateRangePicker value={dateRange} onChange={setDateRange} />

        <div className="flex items-center gap-2">
          <Checkbox
            id="complex-only"
            checked={complexOnly}
            onCheckedChange={(checked) => setComplexOnly(checked === true)}
          />
          <Label htmlFor="complex-only" className="cursor-pointer font-normal">
            Complex contribution only
          </Label>
        </div>
      </div>

      {categoryTotals.size > 0 ? (
        <div className="flex flex-wrap gap-3 text-sm" data-testid="category-totals">
          {Array.from(categoryTotals.entries()).map(([cat, total]) => (
            <div key={cat} className="rounded-md border border-border bg-card px-3 py-1.5">
              <span className="text-muted-foreground">{CATEGORY_LABEL[cat]}:</span>{" "}
              <span className="font-medium text-foreground">{formatCurrency(total)}</span>
            </div>
          ))}
        </div>
      ) : null}

      <DataTable
        columns={columns}
        data={expenditures}
        isLoading={expendituresQuery.isLoading}
        emptyMessage="No expenditures recorded yet."
      />
    </div>
  );
}
