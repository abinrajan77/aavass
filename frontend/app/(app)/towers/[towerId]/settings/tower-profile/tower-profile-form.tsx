"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { toast } from "sonner";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ActiveStateBadge } from "@/components/status-badge";
import { Can } from "@/components/auth/can";
import { PERMISSIONS } from "@/lib/permissions";
import { getTower, updateTower, deactivateTower } from "@/lib/api/towers";

// Subset of createTowerSchema (frontend.md) applicable to an edit of an
// already-created tower — `code` is immutable post-creation since it's baked
// into Module 3's receipt numbering.
const editTowerSchema = z.object({
  name: z.string().min(1).max(100),
  totalFloors: z.number().int().positive(),
  totalFlats: z.number().int().positive(),
  associationName: z.string().min(1).max(200),
});
type EditTowerInput = z.infer<typeof editTowerSchema>;

export function TowerProfileForm({ towerId }: { towerId: string }) {
  const queryClient = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const { data: tower, isLoading } = useQuery({
    queryKey: ["tower", towerId],
    queryFn: () => getTower(towerId),
  });

  const form = useForm<EditTowerInput>({
    resolver: zodResolver(editTowerSchema),
    defaultValues: { name: "", totalFloors: 1, totalFlats: 1, associationName: "" },
  });

  useEffect(() => {
    if (tower) {
      form.reset({
        name: tower.name,
        totalFloors: tower.total_floors,
        totalFlats: tower.total_flats,
        associationName: tower.association_name,
      });
    }
  }, [tower, form]);

  const updateMutation = useMutation({
    mutationFn: (values: EditTowerInput) =>
      updateTower(towerId, {
        name: values.name,
        total_floors: values.totalFloors,
        total_flats: values.totalFlats,
        association_name: values.associationName,
      }),
    onSuccess: () => {
      toast.success("Tower profile updated");
      queryClient.invalidateQueries({ queryKey: ["tower", towerId] });
    },
    onError: () => toast.error("Couldn't update tower profile"),
  });

  const deactivateMutation = useMutation({
    mutationFn: () => deactivateTower(towerId),
    onSuccess: () => {
      toast.success("Tower deactivated");
      setConfirmOpen(false);
      queryClient.invalidateQueries({ queryKey: ["tower", towerId] });
    },
    onError: (err: unknown) => {
      const message =
        err && typeof err === "object" && "message" in err ? String((err as Error).message) : undefined;
      toast.error(message ?? "Couldn't deactivate tower (it may have active dues)");
      setConfirmOpen(false);
    },
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-40" />
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle>Tower profile</CardTitle>
          <CardDescription>Name, floors, flat count, association name.</CardDescription>
        </div>
        {tower ? <ActiveStateBadge deactivatedAt={tower.deactivated_at} /> : null}
      </CardHeader>
      <Form {...form}>
        <form onSubmit={form.handleSubmit((v) => updateMutation.mutate(v))}>
          <CardContent className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Tower name</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="associationName"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Association name</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="totalFloors"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Total floors</FormLabel>
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
                name="totalFlats"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Total flats</FormLabel>
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
            </div>
          </CardContent>
          <CardFooter className="flex items-center justify-between">
            <Can permission={PERMISSIONS.MANAGE_COMPLEX}>
              <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
                <DialogTrigger asChild>
                  <Button type="button" variant="outline" className="text-destructive hover:text-destructive">
                    Deactivate tower
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Deactivate this tower?</DialogTitle>
                    <DialogDescription>
                      Blocked if any Pending/Overdue due exists (409 TOWER_HAS_ACTIVE_FINANCIALS).
                      Financial history remains intact either way.
                    </DialogDescription>
                  </DialogHeader>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setConfirmOpen(false)}>
                      Cancel
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={() => deactivateMutation.mutate()}
                      disabled={deactivateMutation.isPending}
                    >
                      Deactivate
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </Can>
            <Can permission={PERMISSIONS.MANAGE_COMPLEX}>
              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? "Saving..." : "Save changes"}
              </Button>
            </Can>
          </CardFooter>
        </form>
      </Form>
    </Card>
  );
}
