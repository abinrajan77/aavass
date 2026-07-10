"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { OccupancyStatusBadge } from "@/components/status-badge";
import { Can } from "@/components/auth/can";
import { OwnersTab } from "@/components/flats/owners-tab";
import { TenantsTab } from "@/components/flats/tenants-tab";
import { useSession } from "@/components/providers/session-provider";
import { PERMISSIONS } from "@/lib/permissions";
import { ownerContactUpdateSchema, type OwnerContactUpdate } from "@/lib/schemas/owner";
import {
  useFlatOwnersQuery,
  useMyFlatsQuery,
  useUpdateOwnerContactMutation,
} from "@/lib/hooks/use-flats";
import type { ApiError } from "@/lib/api/client";

/**
 * Owner self-service equivalent of the admin flat detail page —
 * frontend.md: same three Tabs, permission-scoped.
 *
 *   - Details: flat fields (flat_number/floor/type/carpet_area_sqft) render
 *     as plain text — NEVER an <input> — per the "must NOT break" rule that
 *     identity/admin-only fields must never render as editable inputs here,
 *     even after a future refactor. Below that, an editable contact Form
 *     (phone/email only — MANAGE_OWN_FLAT's OwnerContactUpdate schema has no
 *     other fields to begin with).
 *   - Owners: read-only (no add/remove/primary-contact controls).
 *   - Tenants: full parity with the admin view (owners may add/vacate their
 *     own flat's tenant).
 */
export function MyFlatClient({ flatId }: { flatId: string }) {
  const session = useSession();
  const myFlatsQuery = useMyFlatsQuery();

  if (myFlatsQuery.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const flat = myFlatsQuery.data?.find((f) => f.id === flatId);

  if (!flat) {
    return (
      <div className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
        This flat isn&apos;t one you currently own, or it couldn&apos;t be found.
      </div>
    );
  }

  return (
    <FlatOwnerView towerId={flat.tower_id} flatId={flatId} sessionUserId={session?.user.id} />
  );
}

function FlatOwnerView({
  towerId,
  flatId,
  sessionUserId,
}: {
  towerId: string;
  flatId: string;
  sessionUserId: string | undefined;
}) {
  const myFlatsQuery = useMyFlatsQuery();
  const ownersQuery = useFlatOwnersQuery(towerId, flatId);
  const updateContactMutation = useUpdateOwnerContactMutation(towerId, flatId);

  const flat = myFlatsQuery.data?.find((f) => f.id === flatId);
  // Owner.user_id links the Owner row to the logged-in User — see
  // lib/api/types.ts's `Owner.user_id` comment for why this match is needed.
  const myOwnership = ownersQuery.data?.find(
    (o) => !o.date_to && o.owner.user_id && o.owner.user_id === sessionUserId
  );

  const form = useForm<OwnerContactUpdate>({
    resolver: zodResolver(ownerContactUpdateSchema),
    defaultValues: { phone: "", email: "" },
  });

  useEffect(() => {
    if (myOwnership) {
      form.reset({ phone: myOwnership.owner.phone, email: myOwnership.owner.email ?? "" });
    }
  }, [myOwnership, form]);

  if (!flat) return null;

  function onSubmit(values: OwnerContactUpdate) {
    if (!myOwnership) return;
    updateContactMutation.mutate(
      { ownerId: myOwnership.owner_id, input: { phone: values.phone, email: values.email || undefined } },
      {
        onSuccess: () => toast.success("Contact details updated"),
        onError: (err) => {
          const apiErr = err as ApiError;
          toast.error(apiErr?.message ?? "Couldn't update contact details");
        },
      }
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold text-foreground">
          Flat {flat.flat_number} · Floor {flat.floor} · {flat.type}
        </h1>
        <OccupancyStatusBadge status={flat.occupancy_status} />
      </div>

      <Tabs defaultValue="details">
        <TabsList>
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="owners">Owners</TabsTrigger>
          <TabsTrigger value="tenants">Tenants</TabsTrigger>
        </TabsList>

        <TabsContent value="details" className="space-y-4">
          <Card>
            <CardContent className="grid grid-cols-2 gap-3 pt-6 text-sm">
              <div>
                <p className="text-muted-foreground">Flat number</p>
                <p className="text-foreground">{flat.flat_number}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Floor</p>
                <p className="text-foreground">{flat.floor}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Type</p>
                <p className="text-foreground">{flat.type}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Carpet area</p>
                <p className="text-foreground">{flat.carpet_area_sqft} sqft</p>
              </div>
            </CardContent>
          </Card>

          {myOwnership ? (
            <Card>
              <CardContent className="pt-6">
                <Can permission={PERMISSIONS.MANAGE_OWN_FLAT}>
                  <Form {...form}>
                    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                      <FormField
                        control={form.control}
                        name="phone"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Phone</FormLabel>
                            <FormControl>
                              <Input {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="email"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Email</FormLabel>
                            <FormControl>
                              <Input type="email" {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <Button type="submit" disabled={updateContactMutation.isPending}>
                        {updateContactMutation.isPending ? "Saving..." : "Save contact details"}
                      </Button>
                    </form>
                  </Form>
                </Can>
              </CardContent>
            </Card>
          ) : null}
        </TabsContent>

        <TabsContent value="owners">
          <OwnersTab towerId={towerId} flatId={flatId} canManage={false} />
        </TabsContent>

        <TabsContent value="tenants">
          <TenantsTab towerId={towerId} flatId={flatId} canManage />
        </TabsContent>
      </Tabs>
    </div>
  );
}
