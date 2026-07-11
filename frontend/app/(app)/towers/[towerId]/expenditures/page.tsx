import { ExpendituresClient } from "./expenditures-client";

export default function ExpendituresPage({ params }: { params: { towerId: string } }) {
  return <ExpendituresClient towerId={params.towerId} />;
}
