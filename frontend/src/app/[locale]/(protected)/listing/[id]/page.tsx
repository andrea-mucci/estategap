import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { ListingDetailPage } from "@/components/listing/ListingDetailPage";
import { createServerApiClient } from "@/lib/api";
import type { ExtendedListingDetail } from "@/lib/listing-search";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const t = await getTranslations("listingDetail");
  const { id } = await params;
  const client = await createServerApiClient();
  const { data } = await client.GET("/api/v1/listings/{id}", {
    params: {
      path: { id },
    },
  });

  const listing = data as ExtendedListingDetail | undefined;

  return {
    title: listing
      ? `${listing.address ?? listing.city ?? listing.id} · ${listing.asking_price_eur ?? ""}`
      : t("fallbackTitle"),
  };
}

export default async function ListingPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const client = await createServerApiClient();
  const { data, error } = await client.GET("/api/v1/listings/{id}", {
    params: {
      path: { id },
    },
  });

  if (error || !data) {
    notFound();
  }

  return <ListingDetailPage initialListing={data as ExtendedListingDetail} />;
}
