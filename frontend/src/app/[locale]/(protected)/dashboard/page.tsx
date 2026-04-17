import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";

import { DashboardClient } from "@/components/dashboard";
import { requireSession } from "@/lib/auth";
import { fetchCountries, fetchDashboardSummary } from "@/lib/api";

type DashboardPageProps = {
  searchParams?: Promise<{
    country?: string;
  }> | {
    country?: string;
  };
};

export default async function DashboardPage({ searchParams }: DashboardPageProps) {
  const session = await requireSession();
  const queryClient = new QueryClient();
  const params = searchParams ? await Promise.resolve(searchParams) : undefined;
  const country = (params?.country ?? "ES").toUpperCase();

  await queryClient.prefetchQuery({
    queryKey: ["dashboard", "summary", country],
    queryFn: () => fetchDashboardSummary(session.accessToken, country),
  });

  await queryClient.prefetchQuery({
    queryKey: ["countries"],
    queryFn: () => fetchCountries(session.accessToken),
  });

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <DashboardClient country={country} />
    </HydrationBoundary>
  );
}
