"use client";

import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { z } from "zod";
import { Button } from "@/components/ui/button";
import { DialogFooter } from "@/components/ui/dialog";
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DatePickerField } from "@/components/form/date-picker-field";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { formatCurrency } from "@/lib/utils";
import { specialCollectionSchema, type SpecialCollectionInput } from "@/lib/schemas/special-collection";

/**
 * Deterministic equal-split preview, mirroring the backend's rounding rule
 * exactly (specs/04-special-collections-expenditure/backend.md "Equal-split
 * calculation"): whole paise, remainder distributed one extra paisa per flat
 * (first N by flat_number ascending — the preview can't know the ordering,
 * so it only reports counts, not which flats).
 */
function computeSplitPreview(totalAmount: number, flatCount: number) {
  if (!totalAmount || totalAmount <= 0 || !flatCount || flatCount <= 0) return null;
  const totalPaise = Math.round(totalAmount * 100);
  const basePaise = Math.floor(totalPaise / flatCount);
  const remainder = totalPaise % flatCount;
  return {
    flatCount,
    remainder,
    higherCount: remainder,
    lowerCount: flatCount - remainder,
    higherAmount: (basePaise + 1) / 100,
    lowerAmount: basePaise / 100,
  };
}

export function SpecialCollectionForm({
  activeFlatCount,
  activeFlatCountIsFallback,
  onSubmit,
  isSubmitting,
  onCancel,
}: {
  activeFlatCount: number;
  activeFlatCountIsFallback?: boolean;
  onSubmit: (values: SpecialCollectionInput) => void;
  isSubmitting?: boolean;
  onCancel?: () => void;
}) {
  // `total_amount` is `z.coerce.number()`, so react-hook-form's *input* type
  // (raw field values pre-coercion) differs from the *output* type
  // (post-validation, what `onSubmit` receives) — type useForm with both via
  // the 3rd (TTransformedValues) generic, per react-hook-form + zod's
  // documented pattern for z.coerce fields.
  const form = useForm<z.input<typeof specialCollectionSchema>, unknown, SpecialCollectionInput>({
    resolver: zodResolver(specialCollectionSchema),
    defaultValues: { title: "", description: "", total_amount: 0, split_basis: "equal", due_date: undefined },
  });

  const totalAmount = useWatch({ control: form.control, name: "total_amount" });
  const debouncedTotalAmount = useDebouncedValue(totalAmount, 200);
  const preview = computeSplitPreview(Number(debouncedTotalAmount) || 0, activeFlatCount);

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Title</FormLabel>
              <FormControl>
                <Input placeholder="Lift Modernization Fund" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description (optional)</FormLabel>
              <FormControl>
                <Textarea rows={2} {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="total_amount"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Total amount</FormLabel>
              <FormControl>
                <Input
                  type="number"
                  min={0}
                  step="0.01"
                  {...field}
                  value={(field.value as number | string | undefined) ?? ""}
                  onChange={(e) => field.onChange(e.target.value)}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="split_basis"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Split basis</FormLabel>
              <Select value={field.value} disabled>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value="equal">Equal Split</SelectItem>
                </SelectContent>
              </Select>
              <FormDescription>
                v1.0 supports Equal Split only — more split options are planned for a future release.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="due_date"
          render={({ field }) => (
            <FormItem className="flex flex-col">
              <FormLabel>Due date</FormLabel>
              <FormControl>
                <DatePickerField
                  value={field.value}
                  onChange={field.onChange}
                  disabledDate={(date) => date <= new Date()}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div
          data-testid="split-preview"
          className="rounded-md border border-dashed border-border bg-muted/40 p-3 text-sm"
        >
          {preview ? (
            preview.remainder === 0 ? (
              <p>
                ≈ {formatCurrency(preview.lowerAmount)} per flat across {preview.flatCount} flats
              </p>
            ) : (
              <>
                <p>
                  ≈ {formatCurrency(preview.lowerAmount)}–{formatCurrency(preview.higherAmount)} per flat across{" "}
                  {preview.flatCount} flats
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {preview.higherCount} flat{preview.higherCount === 1 ? "" : "s"} at{" "}
                  {formatCurrency(preview.higherAmount)}, {preview.lowerCount} at {formatCurrency(preview.lowerAmount)}{" "}
                  — matches the backend&apos;s remainder-distribution rule.
                </p>
              </>
            )
          ) : (
            <p className="text-muted-foreground">Enter a total amount to preview the per-flat split.</p>
          )}
          {activeFlatCountIsFallback ? (
            <p className="mt-1 text-xs text-muted-foreground">
              Estimated using the tower&apos;s configured flat count — the active-flat-count endpoint (Module 2)
              isn&apos;t live yet.
            </p>
          ) : null}
        </div>

        <DialogFooter>
          {onCancel ? (
            <Button type="button" variant="outline" onClick={onCancel}>
              Cancel
            </Button>
          ) : null}
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Creating..." : "Create special collection"}
          </Button>
        </DialogFooter>
      </form>
    </Form>
  );
}
