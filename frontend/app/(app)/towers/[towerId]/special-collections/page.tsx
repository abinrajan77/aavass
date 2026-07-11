import { SpecialCollectionsClient } from "./special-collections-client";

export default function SpecialCollectionsPage({ params }: { params: { towerId: string } }) {
  return <SpecialCollectionsClient towerId={params.towerId} />;
}
