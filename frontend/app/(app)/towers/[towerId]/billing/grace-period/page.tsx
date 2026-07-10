import { GracePeriodClient } from "./grace-period-client";

export default function GracePeriodPage({ params }: { params: { towerId: string } }) {
  return <GracePeriodClient towerId={params.towerId} />;
}
