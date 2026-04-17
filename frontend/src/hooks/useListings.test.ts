import type { PropsWithChildren } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useListings } from "./useListings";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("useListings", () => {
  it("returns listing data from the contract-backed MSW handler", async () => {
    const { result } = renderHook(() => useListings({ country: "ES" }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.items[0]).toMatchObject({
      id: "6c07c38e-0d03-4c46-96db-74e9f4d1d45d",
      country: "ES",
      city: "Madrid",
      currency: "EUR",
    });
  });
});
