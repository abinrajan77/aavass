"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { OccupancyStatusBadge } from "@/components/status-badge";
import { Can } from "@/components/auth/can";
import { OwnersTab } from "@/components/flats/owners-tab";
import { TenantsTab } from "@/components/flats/tenants-tab";
import { useSession } from "@/components/providers/session-provider";
import { PERMISSIONS } from "@/lib/permissions";
import { FLAT_TYPES, flatUpdateSchema, type FlatUpdate } from "@/lib/schemas/flat";
import {
  useDeactivateFlatMutation,
  useFlatQuery,
  useReactivateFlatMutation,
  useUpdateFlatMutation,
} from "@/lib/hooks/use-flats";
import type { ApiError } from "@/lib/api/client";

/**
 * Admin flat detail page — frontend.md: header (flat_number/floor/type,
 * occupancy Badge, Deactivate/Reactivate) + Tabs (Details/Owners/Tenants).
 * Editing lives in the Details tab's own Form (mirroring the
 * tower-profile-form.tsx precedent — a single inline editable Card, no
 * separate header "Edit" trigger that would otherwise duplicate the same
 * action).
 */
export function FlatDetailClient({ towerId, flatId }: { towerId: string; flatId: string }) {
  const session = useSession();
  const canManageResidents = session?.permissions.includes(PERMISSIONS.MANAGE_RESIDENTS) ?? false;

  const flatQuery = useFlatQuery(towerId, flatId);
  const updateFlatMutation = useUpdateFlatMutation(towerId, flatId);
  const deactivateFlatMutation = useDeactivateFlatMutation(towerId, flatId);
  const reactivateFlatMutation = useReactivateFlatMutation(towerId, flatId);

  const form = useForm<FlatUpdate>({
    resolver: zodResolver(flatUpdateSchema),
    defaultValues: { flat_number: "", floor: 1, type: "1BHK", carpet_area_sqft: 0 },
  });

  useEffect(() => {
    if (flatQuery.data) {
      form.reset({
        flat_number: flatQuery.data.flat_number,
        floor: flatQuery.data.floor,
        type: flatQuery.data.type,
        carpet_area_sqft: flatQuery.data.carpet_area_sqft,
      });
    }
  }, [flatQuery.data, form]);

  if (flatQuery.isLoading || !flatQuery.data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const flat = flatQuery.data;

  function onSubmit(values: FlatUpdate) {
    updateFlatMutation.mutate(values, {
      onSuccess: () => toast.success("Flat updated"),
      onError: (err) => {
        const apiErr = err as ApiError;
        toast.error(
          apiErr?.errorCode === "IMMUTABLE_RECORD"
            ? "This flat is deactivated and can't be edited."
            : apiErr?.message ?? "Couldn't update flat"
        );
      },
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-foreground">
            Flat {flat.flat_number} · Floor {flat.floor} · {flat.type}
          </h1>
          <OccupancyStatusBadge status={flat.occupancy_status} />
        </div>
        <Can permission={PERMISSIONS.MANAGE_RESIDENTS}>
          {!flat.deactivated_at ? (
            <Button
              variant="outline"
              className="text-destructive hover:text-destructive"
              disabled={deactivateFlatMutation.isPending}
              onClick={() =>
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
            </Button>
          ) : (
            <Button
              variant="outline"
              disabled={reactivateFlatMutation.isPending}
              onClick={() =>
                reactivateFlatMutation.mutate(undefined, {
                  onSuccess: () => toast.success("Flat reactivated"),
                  onError: () => toast.error("Couldn't reactivate flat"),
                })
              }
            >
              Reactivate
            </Button>
          )}
        </Can>
      </div>

      <Tabs defaultValue="details">
        <TabsList>
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="owners">Owners</TabsTrigger>
          <TabsTrigger value="tenants">Tenants</TabsTrigger>
        </TabsList>

        <TabsContent value="details">
          <Card>
            <CardContent className="pt-6">
              <Form {...form}>
                <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                  <FormField
                    control={form.control}
                    name="flat_number"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Flat number</FormLabel>
                        <FormControl>
                          <Input {...field} disabled={!canManageResidents} />
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
                              disabled={!canManageResidents}
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
                          <Select onValueChange={field.onChange} value={field.value} disabled={!canManageResidents}>
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
                            disabled={!canManageResidents}
                            {...field}
                            onChange={(e) => field.onChange(Number(e.target.value))}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <Can permission={PERMISSIONS.MANAGE_RESIDENTS}>
                    <Button type="submit" disabled={updateFlatMutation.isPending || !!flat.deactivated_at}>
                      {updateFlatMutation.isPending ? "Saving..." : "Save changes"}
                    </Button>
                  </Can>
                </form>
              </Form>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="owners">
          <OwnersTab towerId={towerId} flatId={flatId} canManage={canManageResidents} />
        </TabsContent>

        <TabsContent value="tenants">
          <TenantsTab towerId={towerId} flatId={flatId} canManage={canManageResidents} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
