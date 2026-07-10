import { MyFlatClient } from "./my-flat-client";

export default function MyFlatPage({ params }: { params: { flatId: string } }) {
  return (
    <div className="mx-auto max-w-4xl p-6">
      <MyFlatClient flatId={params.flatId} />
    </div>
  );
}
