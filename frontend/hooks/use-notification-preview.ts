import { useQuery } from "@tanstack/react-query";
import { getNotificationPreview } from "@/lib/api/notifications";
import type { NotificationDueType, NotificationEvent } from "@/lib/api/types";

/**
 * specs/05-reporting-owner-portal-notifications/frontend.md §3 —
 * `/towers/[towerId]/notifications/preview/[dueId]`. `retry: false` since a
 * `422` (no resident resolved, backend.md §4 "Logic") is a defensive/expected
 * error state to render inline, not a transient failure to retry.
 */
export function useNotificationPreview(params: {
  event: NotificationEvent | undefined;
  dueId: string | undefined;
  dueType: NotificationDueType | undefined;
}) {
  const { event, dueId, dueType } = params;
  return useQuery({
    queryKey: ["notification-preview", dueId, event, dueType],
    queryFn: () => getNotificationPreview({ event: event as NotificationEvent, due_id: dueId as string, due_type: dueType as NotificationDueType }),
    enabled: Boolean(event && dueId && dueType),
    retry: false,
  });
}
