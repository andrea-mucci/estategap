import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ZoneAnalyticsClient } from "@/components/zones/ZoneAnalyticsClient";
import { createServerApiClient } from "@/lib/api";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const client = await createServerApiClient();
  const { data } = await client.GET("/api/v1/zones/{id}", {
    params: {
      path: { id },
    },
  });

  if (!data) {
    return {
      title: "Zone analytics",
    };
  }

  return {
    title: `${data.name} analytics`,
  };
}

export default async function ZoneDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const client = await createServerApiClient();
  const { data, error } = await client.GET("/api/v1/zones/{id}", {
    params: {
      path: { id },
    },
  });

  if (error || !data) {
    notFound();
  }

  return <ZoneAnalyticsClient initialZone={data} zoneId={id} />;
}
