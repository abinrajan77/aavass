import { TowersClient } from "./towers-client";

export default function ComplexTowersPage({ params }: { params: { complexId: string } }) {
  return <TowersClient complexId={params.complexId} />;
}
