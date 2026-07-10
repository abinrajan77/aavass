import { CycleDetailClient } from "./cycle-detail-client";

export default function CycleDetailPage({ params }: { params: { towerId: string; cycleId: string } }) {
  return <CycleDetailClient towerId={params.towerId} cycleId={params.cycleId} />;
}
