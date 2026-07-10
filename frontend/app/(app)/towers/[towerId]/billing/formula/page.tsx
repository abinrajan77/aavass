import { FormulaClient } from "./formula-client";

export default function FormulaPage({ params }: { params: { towerId: string } }) {
  return <FormulaClient towerId={params.towerId} />;
}
