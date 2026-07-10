import { DuesClient } from "./dues-client";

export default function DuesPage({ params }: { params: { towerId: string } }) {
  return <DuesClient towerId={params.towerId} />;
}
