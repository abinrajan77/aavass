import { AssociationMembersClient } from "./association-members-client";

export default function AssociationMembersPage({ params }: { params: { towerId: string } }) {
  return <AssociationMembersClient towerId={params.towerId} />;
}
