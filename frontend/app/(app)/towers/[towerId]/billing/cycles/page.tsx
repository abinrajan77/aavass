import { CyclesClient } from "./cycles-client";

export default function CyclesPage({ params }: { params: { towerId: string } }) {
  return <CyclesClient towerId={params.towerId} />;
}
