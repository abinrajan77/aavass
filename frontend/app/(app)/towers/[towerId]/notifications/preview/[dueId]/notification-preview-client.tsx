"use client";

import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Copy, User } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AnimatedList } from "@/components/magicui/animated-list";
import { useNotificationPreview } from "@/hooks/use-notification-preview";
import { ApiError } from "@/lib/api/client";
import type { NotificationDueType, NotificationEvent, NotificationMessage } from "@/lib/api/types";

const EVENT_VALUES: NotificationEvent[] = ["due_generated", "overdue_reminder", "payment_confirmed"];
const DUE_TYPE_VALUES: NotificationDueType[] = ["maintenance", "special_collection"];

function isEvent(value: string | null): value is NotificationEvent {
  return EVENT_VALUES.includes(value as NotificationEvent);
}
function isDueType(value: string | null): value is NotificationDueType {
  return DUE_TYPE_VALUES.includes(value as NotificationDueType);
}

const RECIPIENT_LABEL: Record<NotificationMessage["recipient"], string> = {
  tenant: "Tenant",
  owner: "Owner",
};

function MessageCard({ message }: { message: NotificationMessage }) {
  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(message.message_text);
      toast.success("Copied to clipboard");
    } catch {
      toast.error("Couldn't copy to clipboard");
    }
  }

  return (
    <Card data-testid="notification-message-card">
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <div className="flex items-center gap-2">
          <User className="h-4 w-4 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium text-foreground">
              {message.recipient_name}{" "}
              <span className="font-normal text-muted-foreground">({RECIPIENT_LABEL[message.recipient]})</span>
            </p>
            <p className="text-xs text-muted-foreground">{message.recipient_phone}</p>
          </div>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => void handleCopy()}>
          <Copy className="mr-2 h-3.5 w-3.5" />
          Copy
        </Button>
      </CardHeader>
      <CardContent>
        <pre className="whitespace-pre-wrap rounded-md bg-muted p-3 font-mono text-sm text-foreground">
          {message.message_text}
        </pre>
      </CardContent>
    </Card>
  );
}

/**
 * `/towers/[towerId]/notifications/preview/[dueId]` — specs/05-reporting-
 * owner-portal-notifications/frontend.md §3. Accepts `?event=...&due_type=...`
 * query params (set by the "Notify" action button on Module 3/4's due detail
 * views, not owned by this module). No send/dispatch button anywhere — the
 * Copy affordance is the entire v1.0 interaction, per the non-goal "no
 * automated SMS/WhatsApp dispatch."
 */
export function NotificationPreviewClient({ towerId, dueId }: { towerId: string; dueId: string }) {
  const searchParams = useSearchParams();
  const eventParam = searchParams.get("event");
  const dueTypeParam = searchParams.get("due_type");

  const event = isEvent(eventParam) ? eventParam : undefined;
  const dueType = isDueType(dueTypeParam) ? dueTypeParam : undefined;

  const previewQuery = useNotificationPreview({ event, dueId, dueType });

  if (!event || !dueType) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Missing or invalid notification parameters</AlertTitle>
        <AlertDescription>
          This link is missing a valid <code>event</code> and/or <code>due_type</code> query parameter.
        </AlertDescription>
      </Alert>
    );
  }

  if (previewQuery.isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (previewQuery.isError) {
    const err = previewQuery.error;
    const isNoResident = err instanceof ApiError && err.status === 422;
    return (
      <Alert variant="destructive">
        <AlertTitle>Couldn&apos;t prepare this notification</AlertTitle>
        <AlertDescription>
          {isNoResident
            ? "This due has no resident assigned, so a notification message can't be drafted."
            : "Something went wrong loading the notification preview. Try again."}
        </AlertDescription>
      </Alert>
    );
  }

  const messages = previewQuery.data?.messages ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-foreground">Notification preview</h1>
        <p className="text-sm text-muted-foreground">
          Flat {previewQuery.data?.flat_number} · Tower {towerId} — copy the drafted message(s) below to send via
          your own WhatsApp/SMS channel. No message is sent automatically.
        </p>
      </div>

      {messages.length === 0 ? (
        <div className="rounded-md border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
          No messages to preview.
        </div>
      ) : (
        <AnimatedList>
          {messages.map((message, idx) => (
            <MessageCard key={`${message.recipient}-${idx}`} message={message} />
          ))}
        </AnimatedList>
      )}
    </div>
  );
}
