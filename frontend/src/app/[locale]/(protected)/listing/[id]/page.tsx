import { ListingDetailView } from "@/components/listings/ListingDetailView";

export default async function ListingPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return <ListingDetailView id={id} />;
}
