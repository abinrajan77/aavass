import { ExpenditureForm } from "./expenditure-form";

export default function NewExpenditurePage({
  params,
  searchParams,
}: {
  params: { towerId: string };
  searchParams: { type?: string };
}) {
  return (
    <ExpenditureForm towerId={params.towerId} isComplexContribution={searchParams.type === "complex-contribution"} />
  );
}
