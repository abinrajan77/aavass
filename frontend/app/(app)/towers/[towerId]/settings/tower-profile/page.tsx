import { TowerProfileForm } from "./tower-profile-form";

export default function TowerProfilePage({ params }: { params: { towerId: string } }) {
  return (
    <div className="mx-auto max-w-2xl">
      <TowerProfileForm towerId={params.towerId} />
    </div>
  );
}
