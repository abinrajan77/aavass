import { CollectionDetailClient } from "./collection-detail-client";

export default function SpecialCollectionDetailPage({ params }: { params: { towerId: string; id: string } }) {
  return <CollectionDetailClient towerId={params.towerId} collectionId={params.id} />;
}
