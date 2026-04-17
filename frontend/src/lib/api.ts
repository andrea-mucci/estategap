import createClient from "openapi-fetch";

import { auth } from "@/auth";
import type { paths } from "@/types/api";

export type ListingsQuery =
  paths["/api/v1/listings"]["get"]["parameters"]["query"];

export const defaultListingsQuery: ListingsQuery = {
  country: "ES",
  limit: 8,
  sort_by: "deal_score",
  sort_dir: "desc",
};

const baseUrl = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080").replace(
  /\/$/,
  "",
);

function attachAuthorizationHeader(accessToken?: string) {
  const client = createClient<paths>({
    baseUrl,
  });

  client.use({
    async onRequest({ request }) {
      if (accessToken) {
        request.headers.set("Authorization", `Bearer ${accessToken}`);
      }

      request.headers.set("Content-Type", "application/json");
      return request;
    },
  });

  return client;
}

export function createApiClient(accessToken?: string) {
  return attachAuthorizationHeader(accessToken);
}

export async function createServerApiClient() {
  const session = await auth();
  return createApiClient(session?.accessToken);
}
