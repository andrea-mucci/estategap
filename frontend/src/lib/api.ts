import createClient from "openapi-fetch";

import { auth } from "@/auth";
import type { components, paths } from "@/types/api";

export type ListingsQuery =
  paths["/api/v1/listings"]["get"]["parameters"]["query"];
export type ListingSummary = components["schemas"]["ListingSummary"];
export type ListingsGeoJSON = components["schemas"]["ListingsGeoJSON"];
export type ListingDetail = components["schemas"]["ListingDetail"];
export type DashboardSummary = components["schemas"]["DashboardSummary"];
export type CountrySummary = components["schemas"]["CountrySummary"];
export type ZoneDetail = components["schemas"]["ZoneDetail"];
export type ZoneAnalytics = components["schemas"]["ZoneAnalytics"];
export type ZoneGeometry = components["schemas"]["ZoneGeometry"];
export type CreateCustomZoneRequest = components["schemas"]["CreateCustomZoneRequest"];
export type PaginatedList<T> = {
  items: T[];
  cursor: string | null;
  total: number;
  hasMore: boolean;
  currency?: string;
};

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

export function normalizePaginatedList<T>(
  payload:
    | T[]
    | {
        data?: T[];
        pagination?: {
          next_cursor?: string | null;
          has_more?: boolean;
        };
        meta?: {
          total_count?: number;
          currency?: string;
        };
      }
    | {
        items?: T[];
        cursor?: string | null;
        total?: number;
      },
): PaginatedList<T> {
  if (Array.isArray(payload)) {
    return {
      items: payload,
      cursor: null,
      total: payload.length,
      hasMore: false,
    };
  }

  if ("data" in payload) {
    const items = payload.data ?? [];
    return {
      items,
      cursor: payload.pagination?.next_cursor ?? null,
      total: payload.meta?.total_count ?? items.length,
      hasMore: Boolean(payload.pagination?.has_more),
      currency: payload.meta?.currency,
    };
  }

  const items = payload.items ?? [];
  return {
    items,
    cursor: payload.cursor ?? null,
    total: payload.total ?? items.length,
    hasMore: Boolean(payload.cursor),
  };
}

function unwrapError(error?: { error?: string } | null, fallback = "Request failed") {
  if (error?.error) {
    return error.error;
  }
  return fallback;
}

export async function fetchListings(accessToken: string | undefined, params: Partial<ListingsQuery> = {}) {
  const client = createApiClient(accessToken);
  const { data, error } = await client.GET("/api/v1/listings", {
    params: {
      query: {
        ...defaultListingsQuery,
        ...params,
      },
    },
  });

  if (error || !data) {
    throw new Error(unwrapError(error, "Failed to load listings"));
  }

  return normalizePaginatedList<ListingSummary>(
    data as components["schemas"]["ListingsResponse"],
  );
}

export async function fetchListingDetail(accessToken: string | undefined, id: string) {
  const client = createApiClient(accessToken);
  const { data, error } = await client.GET("/api/v1/listings/{id}", {
    params: {
      path: { id },
    },
  });

  if (error || !data) {
    throw new Error(unwrapError(error, "Failed to load listing"));
  }

  return data;
}

export async function fetchDashboardSummary(accessToken: string | undefined, country: string) {
  const client = createApiClient(accessToken);
  const { data, error } = await client.GET("/api/v1/dashboard/summary", {
    params: {
      query: {
        country,
      },
    },
  });

  if (error || !data) {
    throw new Error(unwrapError(error, "Failed to load dashboard summary"));
  }

  return data;
}

export async function fetchCountries(accessToken: string | undefined) {
  const client = createApiClient(accessToken);
  const { data, error } = await client.GET("/api/v1/countries");

  if (error || !data) {
    throw new Error(unwrapError(error, "Failed to load countries"));
  }

  return normalizePaginatedList<CountrySummary>(
    data as components["schemas"]["CountryListResponse"],
  );
}

export async function fetchZoneList(
  accessToken: string | undefined,
  country: string,
  limit = 20,
) {
  const client = createApiClient(accessToken);
  const { data, error } = await client.GET("/api/v1/zones", {
    params: {
      query: {
        country,
        limit,
      },
    },
  });

  if (error || !data) {
    throw new Error(unwrapError(error, "Failed to load zones"));
  }

  return normalizePaginatedList<ZoneDetail>(
    data as components["schemas"]["ZoneListResponse"],
  );
}

export async function fetchZoneAnalytics(accessToken: string | undefined, id: string) {
  const client = createApiClient(accessToken);
  const { data, error } = await client.GET("/api/v1/zones/{id}/analytics", {
    params: {
      path: { id },
    },
  });

  if (error || !data) {
    throw new Error(unwrapError(error, "Failed to load zone analytics"));
  }

  return data;
}

export async function fetchZoneGeometry(accessToken: string | undefined, id: string) {
  const client = createApiClient(accessToken);
  const { data, error } = await client.GET("/api/v1/zones/{id}/geometry", {
    params: {
      path: { id },
    },
  });

  if (error || !data) {
    throw new Error(unwrapError(error, "Failed to load zone geometry"));
  }

  return data;
}

export async function fetchMapListings(
  accessToken: string | undefined,
  country: string,
  bounds: string,
) {
  const client = createApiClient(accessToken);
  const { data, error } = await client.GET("/api/v1/listings", {
    params: {
      query: {
        country,
        bounds,
        format: "geojson",
      },
    },
  });

  if (error || !data) {
    throw new Error(unwrapError(error, "Failed to load map listings"));
  }

  return data as ListingsGeoJSON;
}

export async function createCustomZone(
  accessToken: string | undefined,
  payload: CreateCustomZoneRequest,
) {
  const client = createApiClient(accessToken);
  const { data, error } = await client.POST("/api/v1/zones", {
    body: payload,
  });

  if (error || !data) {
    throw new Error(unwrapError(error, "Failed to create custom zone"));
  }

  return data;
}
