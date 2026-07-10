"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { format } from "date-fns";
import { toast } from "sonner";
import type { z } from "zod";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DatePickerField } from "@/components/form/date-picker-field";
import {
  complexContributionSchema,
  expenditureSchema,
  type ComplexContributionInput,
} from "@/lib/schemas/expenditure";
import {
  createComplexContribution,
  createExpenditure,
  getAttachmentUploadUrl,
  uploadFileWithProgress,
} from "@/lib/api/expenditures";
import type { ExpenditureCategory, PaymentMode } from "@/lib/api/types";

const CATEGORY_OPTIONS: { value: ExpenditureCategory; label: string }[] = [
  { value: "cleaning", label: "Cleaning" },
  { value: "security", label: "Security" },
  { value: "repairs", label: "Repairs" },
  { value: "utilities", label: "Utilities" },
  { value: "other", label: "Other" },
];

const PAYMENT_MODE_OPTIONS: { value: PaymentMode; label: string }[] = [
  { value: "cash", label: "Cash" },
  { value: "bank_transfer", label: "Bank transfer" },
  { value: "cheque", label: "Cheque" },
];

// Widest of the two schemas — `complexContributionSchema` is `expenditureSchema.extend(...)`,
// so a single form-value type covers both modes; the `type` query param only
// changes which resolver validates it and which fields render.
//
// `amount`/`complex_total_amount` are `z.coerce.number()`, so the *input*
// type (raw field values pre-coercion) differs from the *output* type
// (post-validation, what `handleSubmit`'s callback and the create mutation
// receive) — type useForm with both via the 3rd (TTransformedValues)
// generic, per react-hook-form + zod's documented pattern for z.coerce
// fields.
type ExpenditureFormInput = z.input<typeof complexContributionSchema>;
type ExpenditureFormValues = ComplexContributionInput;

export function ExpenditureForm({
  towerId,
  isComplexContribution,
}: {
  towerId: string;
  isComplexContribution: boolean;
}) {
  const router = useRouter();
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);

  const form = useForm<ExpenditureFormInput, unknown, ExpenditureFormValues>({
    resolver: zodResolver(isComplexContribution ? complexContributionSchema : expenditureSchema),
    defaultValues: {
      expenditure_date: undefined,
      category: isComplexContribution ? "other" : undefined,
      description: "",
      vendor_payee_name: "",
      amount: 0,
      payment_mode: undefined,
      complex_total_amount: undefined,
      attachment: undefined,
    } as unknown as ExpenditureFormInput,
  });

  const createMutation = useMutation({
    mutationFn: async (values: ExpenditureFormValues) => {
      let attachment_s3_key: string | undefined;
      if (values.attachment) {
        setUploadProgress(0);
        const { upload_url, attachment_s3_key: key } = await getAttachmentUploadUrl(towerId, {
          filename: values.attachment.name,
          content_type: values.attachment.type,
        });
        await uploadFileWithProgress(upload_url, values.attachment, setUploadProgress);
        attachment_s3_key = key;
      }

      const expenditure_date = format(values.expenditure_date, "yyyy-MM-dd");

      if (isComplexContribution) {
        return createComplexContribution(towerId, {
          expenditure_date,
          description: values.description,
          vendor_payee_name: values.vendor_payee_name,
          complex_total_amount: values.complex_total_amount ?? null,
          amount: values.amount,
          payment_mode: values.payment_mode,
          category: values.category,
          attachment_s3_key,
        });
      }

      return createExpenditure(towerId, {
        expenditure_date,
        category: values.category,
        description: values.description,
        vendor_payee_name: values.vendor_payee_name,
        amount: values.amount,
        payment_mode: values.payment_mode,
        attachment_s3_key,
      });
    },
    onSuccess: () => {
      toast.success(isComplexContribution ? "Complex contribution recorded" : "Expenditure recorded");
      router.push(`/towers/${towerId}/expenditures`);
    },
    onError: () => {
      toast.error("Couldn't save expenditure");
      setUploadProgress(null);
    },
  });

  const attachment = form.watch("attachment");

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>{isComplexContribution ? "Record complex contribution" : "Record expenditure"}</CardTitle>
        <CardDescription>
          {isComplexContribution
            ? "Only the tower's share posts to this tower's books."
            : "Recorded expenditures appear in this tower's expense books."}
        </CardDescription>
      </CardHeader>
      <Form {...form}>
        <form onSubmit={form.handleSubmit((values) => createMutation.mutate(values))}>
          <CardContent className="space-y-4">
            <FormField
              control={form.control}
              name="expenditure_date"
              render={({ field }) => (
                <FormItem className="flex flex-col">
                  <FormLabel>Date</FormLabel>
                  <FormControl>
                    <DatePickerField value={field.value} onChange={field.onChange} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {isComplexContribution ? (
              <FormField
                control={form.control}
                name="complex_total_amount"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Total Complex Expense Amount (optional, for reference)</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min={0}
                        step="0.01"
                        {...field}
                        value={(field.value as number | string | undefined) ?? ""}
                        onChange={(e) => field.onChange(e.target.value === "" ? undefined : e.target.value)}
                      />
                    </FormControl>
                    <FormDescription>Only the tower&apos;s share posts to this tower&apos;s books.</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            ) : null}

            <FormField
              control={form.control}
              name="category"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Category</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select a category" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {CATEGORY_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Textarea rows={2} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="vendor_payee_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Vendor/Payee name</FormLabel>
                  <FormControl>
                    <Input placeholder="ABC Elevators Pvt Ltd" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="amount"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{isComplexContribution ? "Tower's Share Amount" : "Amount"}</FormLabel>
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
              name="payment_mode"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Payment mode</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select a payment mode" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {PAYMENT_MODE_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="attachment"
              // eslint-disable-next-line @typescript-eslint/no-unused-vars -- destructured out so `value` (a File) is never spread onto the native file input, which React forbids controlling.
              render={({ field: { value, onChange, ...rest } }) => (
                <FormItem>
                  <FormLabel>Attachment (optional)</FormLabel>
                  <FormControl>
                    <Input
                      type="file"
                      accept=".pdf,.jpg,.jpeg,.png"
                      onChange={(e) => {
                        onChange(e.target.files?.[0]);
                        void form.trigger("attachment");
                      }}
                      {...rest}
                    />
                  </FormControl>
                  {attachment ? (
                    <FormDescription>
                      {attachment.name} · {(attachment.size / (1024 * 1024)).toFixed(2)} MB
                    </FormDescription>
                  ) : null}
                  <FormMessage />
                </FormItem>
              )}
            />

            {uploadProgress !== null ? (
              <div className="space-y-1">
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary transition-all"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
                <p className="text-xs text-muted-foreground">Uploading attachment… {uploadProgress}%</p>
              </div>
            ) : null}
          </CardContent>
          <CardFooter className="justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => router.push(`/towers/${towerId}/expenditures`)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Saving..." : isComplexContribution ? "Record contribution" : "Record expenditure"}
            </Button>
          </CardFooter>
        </form>
      </Form>
    </Card>
  );
}
