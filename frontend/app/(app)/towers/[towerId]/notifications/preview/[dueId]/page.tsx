import { NotificationPreviewClient } from "./notification-preview-client";

export default function NotificationPreviewPage({
  params,
}: {
  params: { towerId: string; dueId: string };
}) {
  return <NotificationPreviewClient towerId={params.towerId} dueId={params.dueId} />;
}
