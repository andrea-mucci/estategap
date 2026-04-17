import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";

import { DashboardOverview } from "@/components/listings/DashboardOverview";
import { createServerApiClient, defaultListingsQuery } from "@/lib/api";

export default async function DashboardPage() {
  const queryClient = new QueryClient();
  const client = await createServerApiClient();

  await queryClient.prefetchQuery({
    queryKey: ["listings", {}],
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/listings", {
        params: {
          query: defaultListingsQuery,
        },
      });

      if (error) {
        throw new Error(error.error || "Failed to load listings");
      }

      return data;
    },
  });

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <DashboardOverview />
    </HydrationBoundary>
  );
}
