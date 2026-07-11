import { FlatDashboardClient } from "./dashboard-client";

export default function FlatDashboardPage({ params }: { params: { flatId: string } }) {
  return <FlatDashboardClient flatId={params.flatId} />;
}
