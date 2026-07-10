import { FlatDetailClient } from "./flat-detail-client";

export default function FlatDetailPage({ params }: { params: { towerId: string; flatId: string } }) {
  return <FlatDetailClient towerId={params.towerId} flatId={params.flatId} />;
}
