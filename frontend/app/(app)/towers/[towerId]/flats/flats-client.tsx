"use client";

import { useState } from "react";
import Link from "next/link";
import { ColumnDef } from "@tanstack/react-table";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { MoreHorizontal } from "lucide-react";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { OccupancyStatusBadge } from "@/components/status-badge";
import { Can } from "@/components/auth/can";
import { PERMISSIONS } from "@/lib/permissions";
import { FLAT_TYPES, flatCreateSchema, type FlatCreate } from "@/lib/schemas/flat";
import {
  useCreateFlatMutation,
  useDeactivateFlatMutation,
  useFlatsQuery,
  useReactivateFlatMutation,
} from "@/lib/hooks/use-flats";
import type { ApiError } from "@/lib/api/client";
import type { Flat, FlatType, OccupancyStatus } from "@/lib/api/types";

const OCCUPANCY_FILTERS: { value: OccupancyStatus; label: string }[] = [
  { value: "vacant", label: "Vacant" },
  { value: "owner_occupied", label: "Owner-occupied" },
  { value: "tenant_occupied", label: "Tenant-occupied" },
];

const ALL = "__all__";

export function FlatsClient({ towerId }: { towerId: string }) {
  const [createOpen, setCreateOpen] = useState(false);
  const [detailFlat, setDetailFlat] = useState<Flat | null>(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>(ALL);
  const [occupancyFilter, setOccupancyFilter] = useState<string>(ALL);

  const flatsQuery = useFlatsQuery(towerId, {
    q: search || undefined,
    type: typeFilter === ALL ? undefined : (typeFilter as FlatType),
    occupancy_status: occupancyFilter === ALL ? undefined : (occupancyFilter as OccupancyStatus),
  });

  const createFlatMutation = useCreateFlatMutation(towerId);
  const deactivateFlatMutation = useDeactivateFlatMutation(towerId, detailFlat?.id ?? "");
  const reactivateFlatMutation = useReactivateFlatMutation(towerId, detailFlat?.id ?? "");

  const form = useForm<FlatCreate>({
    resolver: zodResolver(flatCreateSchema),
    defaultValues: { flat_number: "", floor: 1, type: "1BHK", carpet_area_sqft: 0 },
  });

  function submitCreateFlat(values: FlatCreate) {
    createFlatMutation.mutate(values, {
      onSuccess: () => {
        toast.success("Flat created");
        setCreateOpen(false);
        form.reset();
      },
      onError: (err) => {
        const apiErr = err as ApiError;
        toast.error(apiErr?.message ?? "Couldn't create flat");
      },
    });
  }

  const columns: ColumnDef<Flat>[] = [
    {
      accessorKey: "flat_number",
      header: "Flat No.",
      cell: ({ row }) => (
        <Link
          href={`/towers/${towerId}/flats/${row.original.id}`}
          className="text-primary hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          {row.original.flat_number}
        </Link>
      ),
    },
    { accessorKey: "floor", header: "Floor" },
    { accessorKey: "type", header: "Type" },
    { accessorKey: "carpet_area_sqft", header: "Carpet Area (sqft)" },
    {
      id: "occupancy_status",
      header: "Occupancy",
      cell: ({ row }) => <OccupancyStatusBadge status={row.original.occupancy_status} />,
    },
    {
      id: "primary_owner",
      header: "Primary Owner",
      cell: ({ row }) => row.original.primary_owner?.full_name ?? "—",
    },
    {
      id: "active_tenant",
      header: "Active Tenant",
      cell: ({ row }) => row.original.active_tenant?.full_name ?? "—",
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" onClick={(e) => e.stopPropagation()}>
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
            <DropdownMenuItem asChild>
              <Link href={`/towers/${towerId}/flats/${row.original.id}`}>View / Edit</Link>
            </DropdownMenuItem>
            <Can permission={PERMISSIONS.MANAGE_RESIDENTS}>
              <FlatDeactivateMenuItem towerId={towerId} flat={row.original} />
            </Can>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Flats</h1>
          <p className="text-sm text-muted-foreground">Flat, owner, and tenant records for this tower.</p>
        </div>
        <Can permission={PERMISSIONS.MANAGE_RESIDENTS}>
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button>Add Flat</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add flat</DialogTitle>
                <DialogDescription>New flats start with occupancy status Vacant.</DialogDescription>
              </DialogHeader>
              <Form {...form}>
                <form onSubmit={form.handleSubmit(submitCreateFlat)} className="space-y-4">
                  <FormField
                    control={form.control}
                    name="flat_number"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Flat number</FormLabel>
                        <FormControl>
                          <Input placeholder="101" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <div className="grid grid-cols-2 gap-4">
                    <FormField
                      control={form.control}
                      name="floor"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Floor</FormLabel>
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
                      name="type"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Type</FormLabel>
                          <Select onValueChange={field.onChange} value={field.value}>
                            <FormControl>
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              {FLAT_TYPES.map((type) => (
                                <SelectItem key={type} value={type}>
                                  {type}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                  <FormField
                    control={form.control}
                    name="carpet_area_sqft"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Carpet area (sqft)</FormLabel>
                        <FormControl>
                          <Input
                            type="number"
                            step="0.01"
                            {...field}
                            onChange={(e) => field.onChange(Number(e.target.value))}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <DialogFooter>
                    <Button type="submit" disabled={createFlatMutation.isPending}>
                      {createFlatMutation.isPending ? "Creating..." : "Add flat"}
                    </Button>
                  </DialogFooter>
                </form>
              </Form>
            </DialogContent>
          </Dialog>
        </Can>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Input
          placeholder="Search flat number..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All types</SelectItem>
            {FLAT_TYPES.map((type) => (
              <SelectItem key={type} value={type}>
                {type}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={occupancyFilter} onValueChange={setOccupancyFilter}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Occupancy status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All occupancy statuses</SelectItem>
            {OCCUPANCY_FILTERS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <DataTable
        columns={columns}
        data={flatsQuery.data?.items ?? []}
        isLoading={flatsQuery.isLoading}
        onRowClick={(flat) => setDetailFlat(flat)}
        emptyMessage="No flats yet."
      />

      <Sheet open={!!detailFlat} onOpenChange={(open) => !open && setDetailFlat(null)}>
        <SheetContent>
          {detailFlat ? (
            <>
              <SheetHeader>
                <SheetTitle>Flat {detailFlat.flat_number}</SheetTitle>
                <SheetDescription>
                  Floor {detailFlat.floor} · {detailFlat.type}
                </SheetDescription>
              </SheetHeader>
              <div className="mt-6 space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Carpet area</span>
                  <span>{detailFlat.carpet_area_sqft} sqft</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Occupancy</span>
                  <OccupancyStatusBadge status={detailFlat.occupancy_status} />
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Primary owner</span>
                  <span>{detailFlat.primary_owner?.full_name ?? "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Active tenant</span>
                  <span>{detailFlat.active_tenant?.full_name ?? "—"}</span>
                </div>
              </div>
              <Button asChild className="mt-6 w-full">
                <Link href={`/towers/${towerId}/flats/${detailFlat.id}`}>View full profile</Link>
              </Button>
              <Can permission={PERMISSIONS.MANAGE_RESIDENTS}>
                {!detailFlat.deactivated_at ? (
                  <Button
                    variant="outline"
                    className="mt-3 w-full text-destructive hover:text-destructive"
                    disabled={deactivateFlatMutation.isPending}
                    onClick={() =>
                      deactivateFlatMutation.mutate(undefined, {
                        onSuccess: () => {
                          toast.success("Flat deactivated");
                          setDetailFlat(null);
                        },
                        onError: (err) => {
                          const apiErr = err as ApiError;
                          toast.error(
                            apiErr?.errorCode === "OPEN_DUES_EXIST"
                              ? "This flat has open dues — resolve them before deactivating."
                              : apiErr?.message ?? "Couldn't deactivate flat"
                          );
                        },
                      })
                    }
                  >
                    Deactivate flat
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    className="mt-3 w-full"
                    disabled={reactivateFlatMutation.isPending}
                    onClick={() =>
                      reactivateFlatMutation.mutate(undefined, {
                        onSuccess: () => {
                          toast.success("Flat reactivated");
                          setDetailFlat(null);
                        },
                        onError: () => toast.error("Couldn't reactivate flat"),
                      })
                    }
                  >
                    Reactivate flat
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

function FlatDeactivateMenuItem({ towerId, flat }: { towerId: string; flat: Flat }) {
  const deactivateFlatMutation = useDeactivateFlatMutation(towerId, flat.id);
  const reactivateFlatMutation = useReactivateFlatMutation(towerId, flat.id);

  if (flat.deactivated_at) {
    return (
      <DropdownMenuItem
        onSelect={() =>
          reactivateFlatMutation.mutate(undefined, {
            onSuccess: () => toast.success("Flat reactivated"),
            onError: () => toast.error("Couldn't reactivate flat"),
          })
        }
      >
        Reactivate
      </DropdownMenuItem>
    );
  }

  return (
    <DropdownMenuItem
      className="text-destructive"
      onSelect={() =>
        deactivateFlatMutation.mutate(undefined, {
          onSuccess: () => toast.success("Flat deactivated"),
          onError: (err) => {
            const apiErr = err as ApiError;
            toast.error(
              apiErr?.errorCode === "OPEN_DUES_EXIST"
                ? "This flat has open dues — resolve them before deactivating."
                : apiErr?.message ?? "Couldn't deactivate flat"
            );
          },
        })
      }
    >
      Deactivate
    </DropdownMenuItem>
  );
}
