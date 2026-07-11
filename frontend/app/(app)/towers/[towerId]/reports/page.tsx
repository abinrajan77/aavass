import { ReportsClient } from "./reports-client";

export default function ReportsPage({ params }: { params: { towerId: string } }) {
  return <ReportsClient towerId={params.towerId} />;
}
