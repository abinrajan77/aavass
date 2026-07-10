import { FlatsClient } from "./flats-client";

export default function FlatsPage({ params }: { params: { towerId: string } }) {
  return <FlatsClient towerId={params.towerId} />;
}
