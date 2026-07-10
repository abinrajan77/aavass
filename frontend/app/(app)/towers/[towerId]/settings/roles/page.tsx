import { RolesClient } from "./roles-client";

export default function RolesPage({ params }: { params: { towerId: string } }) {
  return <RolesClient towerId={params.towerId} />;
}
