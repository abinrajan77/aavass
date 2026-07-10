"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { forgotPasswordSchema, type ForgotPasswordInput } from "@/lib/schemas/auth";
import { forgotPassword } from "@/lib/api/auth";

export function ForgotPasswordForm() {
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<ForgotPasswordInput>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  });

  async function onSubmit(values: ForgotPasswordInput) {
    setSubmitting(true);
    try {
      await forgotPassword(values);
    } finally {
      // Always show the same generic confirmation regardless of outcome —
      // no user enumeration, per overview.md edge cases (backend always 202s).
      setSubmitted(true);
      setSubmitting(false);
    }
  }

  return (
    <Card className="w-full max-w-sm border-none bg-card shadow-xl">
      <CardHeader className="space-y-1 text-center">
        <CardTitle className="text-xl">Reset your password</CardTitle>
        <CardDescription>We&apos;ll send a reset link if an account exists for that email.</CardDescription>
      </CardHeader>
      <CardContent>
        {submitted ? (
          <Alert>
            <AlertDescription>
              If an account exists for that email, a reset link is on its way.
            </AlertDescription>
          </Alert>
        ) : (
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Email</FormLabel>
                    <FormControl>
                      <Input type="email" placeholder="you@association.com" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button
                type="submit"
                disabled={submitting}
                className="w-full bg-accent text-accent-foreground hover:bg-accent/90"
              >
                {submitting ? "Sending..." : "Send reset link"}
              </Button>
            </form>
          </Form>
        )}
      </CardContent>
    </Card>
  );
}
