import { api } from "./client";
import type { NotificationDueType, NotificationEvent, NotificationPreviewResponse } from "./types";

/**
 * Module 5 notification-preview endpoint — backend.md §4. Admin-only
 * (`VIEW_REPORTS`), drafts (never sends) message text for a due's event.
 * Not a top-level tower-scoped route per backend.md's route table (it's
 * `/api/v1/notifications/templates/preview`, not
 * `/api/v1/towers/{tower_id}/notifications/...`) — the `due_id`/`due_type`
 * pair is sufficient for the backend to resolve tower/flat/resident context,
 * mirroring backend.md exactly rather than inventing a tower-nested path.
 */
export function getNotificationPreview(params: {
  event: NotificationEvent;
  due_id: string;
  due_type: NotificationDueType;
}) {
  return api.get<NotificationPreviewResponse>("/api/v1/notifications/templates/preview", { params });
}
