"use client";

import { useState } from "react";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { startOfToday } from "date-fns";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { DatePickerField } from "@/components/billing/date-picker-field";
import {
  MAINTENANCE_FORMULA_ZERO_WARNING,
  maintenanceFormulaSchema,
  type MaintenanceFormulaInput,
} from "@/lib/schemas/billing";

/** Default sample carpet areas for the live preview — frontend.md §2.1: "either
 * hardcoded sample sizes or the tower's actual min/median/max carpet area". */
const DEFAULT_SAMPLE_AREAS = [600, 900, 1200];

export interface FormulaFormProps {
  defaultValues?: Partial<MaintenanceFormulaInput>;
  onSubmit: (values: { base_amount: number; per_sqft_rate: number; effective_from: Date }) => void;
  isSubmitting?: boolean;
  sampleCarpetAreas?: number[];
}

/**
 * Formula config form with a live-calculated preview (frontend.md §2.1) and
 * the "both zero" soft-warning confirm step (overview.md edge case 6).
 *
 * The zod schema (`maintenanceFormulaSchema`) mirrors the backend Pydantic
 * model verbatim, including the cross-field refine that flags base_amount=0
 * AND per_sqft_rate=0. That refine can only ever fire once the individual
 * field constraints already pass (Zod skips a chained `.refine()` on an
 * object schema if the base shape itself failed), so when it's the *only*
 * error present, it's safe to treat it as a confirmable warning rather than
 * a blocking validation error — the resolver already guarantees no other
 * field is invalid in that case.
 */
export function FormulaForm({ defaultValues, onSubmit, isSubmitting, sampleCarpetAreas }: FormulaFormProps) {
  const [pendingZeroWarning, setPendingZeroWarning] = useState<MaintenanceFormulaInput | null>(null);

  const form = useForm<MaintenanceFormulaInput>({
    // Cast needed because zod v4's `z.coerce.*` fields give the resolver an
    // input type of `unknown` (pre-coercion), while the form's field values
    // here are typed as the coerced output — a well-known typing friction
    // between zod v4 + @hookform/resolvers v5, not a runtime issue (the
    // resolver still coerces identically at runtime).
    resolver: zodResolver(maintenanceFormulaSchema) as Resolver<MaintenanceFormulaInput>,
    defaultValues: {
      base_amount: defaultValues?.base_amount ?? 0,
      per_sqft_rate: defaultValues?.per_sqft_rate ?? 0,
      effective_from: defaultValues?.effective_from ?? startOfToday(),
    },
  });

  const baseAmount = form.watch("base_amount") ?? 0;
  const perSqftRate = form.watch("per_sqft_rate") ?? 0;
  const areas = sampleCarpetAreas ?? DEFAULT_SAMPLE_AREAS;

  function computePreview(area: number) {
    const areaComponent = Math.round(area * Number(perSqftRate) * 100) / 100;
    return Math.round((Number(baseAmount) + areaComponent) * 100) / 100;
  }

  function handleValid(values: MaintenanceFormulaInput) {
    onSubmit(values);
  }

  function handleInvalid(errors: typeof form.formState.errors) {
    const errorKeys = Object.keys(errors);
    const isOnlyZeroWarning =
      errorKeys.length === 1 && errorKeys[0] === "base_amount" && errors.base_amount?.message === MAINTENANCE_FORMULA_ZERO_WARNING;

    if (isOnlyZeroWarning) {
      setPendingZeroWarning(form.getValues());
    }
  }

  function confirmZeroWarning() {
    if (!pendingZeroWarning) return;
    form.clearErrors("base_amount");
    onSubmit(pendingZeroWarning);
    setPendingZeroWarning(null);
  }

  return (
    <>
      <Form {...form}>
        <form onSubmit={form.handleSubmit(handleValid, handleInvalid)} className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="base_amount"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Base Amount (₹)</FormLabel>
                  <FormControl>
                    <Input type="number" step="0.01" min={0} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="per_sqft_rate"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Per Sq.Ft. Rate (₹)</FormLabel>
                  <FormControl>
                    <Input type="number" step="0.01" min={0} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>

          <FormField
            control={form.control}
            name="effective_from"
            render={({ field }) => (
              <FormItem className="flex flex-col">
                <FormLabel>Effective from</FormLabel>
                <DatePickerField
                  value={field.value}
                  onChange={field.onChange}
                  disabled={(date) => date < startOfToday()}
                  ariaLabel="Effective from"
                />
                <FormMessage />
              </FormItem>
            )}
          />

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Live preview</CardTitle>
              <CardDescription>
                Monthly Maintenance = Base Amount + Carpet Area × Per Sq.Ft. Rate
              </CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-3 gap-4 text-sm">
                {areas.map((area) => (
                  <div key={area} className="rounded-md border border-border p-3">
                    <dt className="text-muted-foreground">{area} sq.ft.</dt>
                    <dd className="mt-1 text-lg font-semibold text-foreground">
                      ₹{computePreview(area).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                    </dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>

          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving..." : "Save formula"}
          </Button>
        </form>
      </Form>

      <Dialog open={!!pendingZeroWarning} onOpenChange={(open) => !open && setPendingZeroWarning(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Every due will be ₹0</DialogTitle>
            <DialogDescription>{MAINTENANCE_FORMULA_ZERO_WARNING}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPendingZeroWarning(null)}>
              Go back
            </Button>
            <Button onClick={confirmZeroWarning} disabled={isSubmitting}>
              Confirm and save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
