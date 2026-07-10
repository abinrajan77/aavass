"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { DateField } from "./date-field";
import { AddOwnerDialog } from "./add-owner-dialog";
import {
  useFlatOwnersQuery,
  useRemoveFlatOwnershipMutation,
  useUpdateFlatOwnershipMutation,
} from "@/lib/hooks/use-flats";
import type { ApiError } from "@/lib/api/client";
import type { FlatOwnership } from "@/lib/api/types";

/**
 * Owners tab — frontend.md: active co-owners list (name/phone/email,
 * "Primary" badge), "Add Co-owner", row actions "Make Primary Contact" /
 * "Remove", and a read-only collapsed Ownership History table below.
 * `canManage` gates the admin-only mutations (MANAGE_RESIDENTS) — on
 * /my-flats/[flatId] this tab is always read-only per frontend.md
 * ("co-ownership changes ... remain MANAGE_RESIDENTS-only (admin)").
 */
export function OwnersTab({
  towerId,
  flatId,
  canManage,
}: {
  towerId: string;
  flatId: string;
  canManage: boolean;
}) {
  const ownersQuery = useFlatOwnersQuery(towerId, flatId);
  const updateOwnershipMutation = useUpdateFlatOwnershipMutation(towerId, flatId);
  const removeOwnershipMutation = useRemoveFlatOwnershipMutation(towerId, flatId);
  const [removeTarget, setRemoveTarget] = useState<FlatOwnership | null>(null);
  const [effectiveDate, setEffectiveDate] = useState("");
  const [newPrimaryOwnerId, setNewPrimaryOwnerId] = useState<string>("");

  if (ownersQuery.isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  const ownerships = ownersQuery.data ?? [];
  const active = ownerships.filter((o) => !o.date_to);
  const history = ownerships.filter((o) => o.date_to);
  const otherActiveOwners = (excludeId: string) => active.filter((o) => o.id !== excludeId);

  function onApiError(err: unknown, fallback: string) {
    const apiErr = err as ApiError;
    toast.error(apiErr?.message ?? fallback);
  }

  function openRemove(ownership: FlatOwnership) {
    setRemoveTarget(ownership);
    setEffectiveDate("");
    setNewPrimaryOwnerId("");
  }

  function confirmRemove() {
    if (!removeTarget || !effectiveDate) return;
    removeOwnershipMutation.mutate(
      {
        ownershipId: removeTarget.id,
        input: {
          effective_date: effectiveDate,
          new_primary_owner_id: newPrimaryOwnerId || undefined,
        },
      },
      {
        onSuccess: () => {
          toast.success("Owner removed");
          setRemoveTarget(null);
        },
        onError: (err) => onApiError(err, "Couldn't remove owner (they may be the required primary contact)"),
      }
    );
  }

  const candidatesForNewPrimary = removeTarget ? otherActiveOwners(removeTarget.id) : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-foreground">Active owners</h3>
        {canManage ? <AddOwnerDialog towerId={towerId} flatId={flatId} /> : null}
      </div>

      <div className="rounded-md border border-border">
        {active.length === 0 ? (
          <p className="p-4 text-sm text-muted-foreground">No active owners on this flat.</p>
        ) : (
          <ul className="divide-y divide-border">
            {active.map((ownership) => (
              <li key={ownership.id} className="flex items-center justify-between gap-4 p-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-foreground">{ownership.owner.full_name}</span>
                    {ownership.is_primary_contact ? <Badge variant="accent">Primary</Badge> : null}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {ownership.owner.phone}
                    {ownership.owner.email ? ` · ${ownership.owner.email}` : ""}
                  </p>
                </div>
                {canManage ? (
                  <div className="flex gap-2">
                    {!ownership.is_primary_contact ? (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={updateOwnershipMutation.isPending}
                        onClick={() =>
                          updateOwnershipMutation.mutate(
                            { ownershipId: ownership.id, input: { is_primary_contact: true } },
                            {
                              onSuccess: () => toast.success("Primary contact updated"),
                              onError: (err) => onApiError(err, "Couldn't update primary contact"),
                            }
                          )
                        }
                      >
                        Make primary contact
                      </Button>
                    ) : null}
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      onClick={() => openRemove(ownership)}
                    >
                      Remove
                    </Button>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>

      <details className="rounded-md border border-border">
        <summary className="cursor-pointer p-3 text-sm font-medium text-foreground">
          Ownership history ({history.length})
        </summary>
        {history.length === 0 ? (
          <p className="p-4 text-sm text-muted-foreground">No past owners.</p>
        ) : (
          <ul className="divide-y divide-border">
            {history.map((ownership) => (
              <li key={ownership.id} className="p-3 text-sm">
                <span className="font-medium text-foreground">{ownership.owner.full_name}</span>{" "}
                <span className="text-muted-foreground">
                  ({ownership.date_from} — {ownership.date_to})
                </span>
              </li>
            ))}
          </ul>
        )}
      </details>

      <Dialog open={!!removeTarget} onOpenChange={(open) => !open && setRemoveTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove {removeTarget?.owner.full_name}?</DialogTitle>
            <DialogDescription>
              This ends their ownership period (date_to is set) — it is never deleted from history.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Effective date</label>
              <DateField value={effectiveDate} onChange={setEffectiveDate} />
            </div>
            {removeTarget?.is_primary_contact && candidatesForNewPrimary.length > 0 ? (
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  New primary contact (required — this owner is the current primary contact)
                </label>
                <Select value={newPrimaryOwnerId} onValueChange={setNewPrimaryOwnerId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a co-owner" />
                  </SelectTrigger>
                  <SelectContent>
                    {candidatesForNewPrimary.map((o) => (
                      <SelectItem key={o.id} value={o.owner_id}>
                        {o.owner.full_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRemoveTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={
                !effectiveDate ||
                removeOwnershipMutation.isPending ||
                (!!removeTarget?.is_primary_contact && candidatesForNewPrimary.length > 0 && !newPrimaryOwnerId)
              }
              onClick={confirmRemove}
            >
              {removeOwnershipMutation.isPending ? "Removing..." : "Remove owner"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
