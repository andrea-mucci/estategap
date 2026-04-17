import createClient from "openapi-fetch";

import { auth } from "@/auth";
import type {
  ExtendedListingDetail,
  ListingSearchParams,
  ListingStatusFilter,
} from "@/lib/listing-search";
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
export type CrmStatus = "favorite" | "contacted" | "visited" | "offer" | "discard" | null;
export type SavedSearch = {
  created_at: string;
  filters: ListingSearchParams;
  id: string;
  name: string;
  updated_at: string;
};
export type CrmEntry = {
  listing_id: string;
  notes: string;
  status: CrmStatus;
  updated_at: string | null;
};
export type TranslatePayload = {
  cached?: boolean;
  source_lang?: string;
  target_lang: string;
  translated_text: string;
};
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

const CRM_STORAGE_KEY = "estategap_crm_entries";

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

function buildRequestHeaders(accessToken?: string, init?: HeadersInit) {
  const headers = new Headers(init);

  headers.set("Content-Type", "application/json");

  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  return headers;
}

async function parseResponse<T>(response: Response, fallbackMessage: string) {
  if (!response.ok) {
    let message = fallbackMessage;

    try {
      const payload = (await response.json()) as { error?: string };
      message = payload.error ?? fallbackMessage;
    } catch {
      message = fallbackMessage;
    }

    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

async function requestJson<T>(
  path: string,
  {
    accessToken,
    body,
    fallbackMessage,
    method = "GET",
  }: {
    accessToken?: string;
    body?: unknown;
    fallbackMessage: string;
    method?: "GET" | "POST" | "PATCH" | "DELETE";
  },
) {
  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers: buildRequestHeaders(accessToken),
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });

  return parseResponse<T>(response, fallbackMessage);
}

function serializeQueryValue(
  key: string,
  value: unknown,
  searchParams: URLSearchParams,
) {
  if (value === null || value === undefined || value === "") {
    return;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return;
    }

    searchParams.set(key, value.join(","));
    return;
  }

  if (typeof value === "boolean") {
    searchParams.set(key, value ? "true" : "false");
    return;
  }

  searchParams.set(key, `${value}`);
}

function loadLocalCrmEntries() {
  if (typeof window === "undefined") {
    return {} as Record<string, CrmEntry>;
  }

  try {
    const raw = window.localStorage.getItem(CRM_STORAGE_KEY);
    if (!raw) {
      return {};
    }

    return JSON.parse(raw) as Record<string, CrmEntry>;
  } catch {
    return {};
  }
}

function saveLocalCrmEntry(entry: CrmEntry) {
  if (typeof window === "undefined") {
    return entry;
  }

  const entries = loadLocalCrmEntries();
  entries[entry.listing_id] = entry;
  window.localStorage.setItem(CRM_STORAGE_KEY, JSON.stringify(entries));
  return entry;
}

export async function fetchListings(
  accessToken: string | undefined,
  params: Partial<ListingsQuery> &
    Partial<
      ListingSearchParams & {
        currency?: string;
        cursor?: string | null;
        format?: "json" | "geojson";
        limit?: number;
        source_portal?: string[];
        status?: ListingStatusFilter[] | ListingStatusFilter;
      }
    > = {},
): Promise<PaginatedList<ListingSummary>> {
  const query = new URLSearchParams();

  for (const [key, value] of Object.entries({
    ...defaultListingsQuery,
    ...params,
  })) {
    serializeQueryValue(key, value, query);
  }

  const response = await fetch(`${baseUrl}/api/v1/listings?${query.toString()}`, {
    headers: buildRequestHeaders(accessToken),
    cache: "no-store",
  });

  const data = await parseResponse<components["schemas"]["ListingsResponse"]>(
    response,
    "Failed to load listings",
  );

  return normalizePaginatedList<ListingSummary>(data);
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

  return data as ExtendedListingDetail;
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
  const query = new URLSearchParams({
    country,
    limit: `${limit}`,
  });
  const response = await fetch(`${baseUrl}/api/v1/zones?${query.toString()}`, {
    headers: buildRequestHeaders(accessToken),
    cache: "no-store",
  });
  const data = await parseResponse<components["schemas"]["ZoneListResponse"]>(
    response,
    "Failed to load zones",
  );

  return normalizePaginatedList<ZoneDetail>(data);
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

export async function searchZoneList(
  accessToken: string | undefined,
  params: {
    country: string;
    level?: number | string;
    limit?: number;
    parent_id?: string;
    q?: string;
  },
) {
  const query = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    serializeQueryValue(key, value, query);
  }

  const response = await fetch(`${baseUrl}/api/v1/zones?${query.toString()}`, {
    headers: buildRequestHeaders(accessToken),
    cache: "no-store",
  });
  const data = await parseResponse<components["schemas"]["ZoneListResponse"]>(
    response,
    "Failed to load zones",
  );

  return normalizePaginatedList<ZoneDetail>(data);
}

export async function fetchSavedSearches(accessToken: string | undefined) {
  const payload = await requestJson<{ data?: SavedSearch[] }>("/api/v1/saved-searches", {
    accessToken,
    fallbackMessage: "Failed to load saved searches",
  });

  return payload.data ?? [];
}

export async function createSavedSearch(
  accessToken: string | undefined,
  payload: Pick<SavedSearch, "filters" | "name">,
) {
  return requestJson<SavedSearch>("/api/v1/saved-searches", {
    accessToken,
    body: payload,
    fallbackMessage: "Failed to create saved search",
    method: "POST",
  });
}

export async function deleteSavedSearch(accessToken: string | undefined, id: string) {
  await requestJson<void>(`/api/v1/saved-searches/${id}`, {
    accessToken,
    fallbackMessage: "Failed to delete saved search",
    method: "DELETE",
  });
}

export async function fetchCrmEntry(accessToken: string | undefined, listingId: string) {
  try {
    return await requestJson<CrmEntry>(`/api/v1/listings/${listingId}/crm`, {
      accessToken,
      fallbackMessage: "Failed to load CRM entry",
    });
  } catch {
    const localEntries = loadLocalCrmEntries();
    return (
      localEntries[listingId] ?? {
        listing_id: listingId,
        notes: "",
        status: null,
        updated_at: null,
      }
    );
  }
}

export async function fetchCrmBulk(accessToken: string | undefined, listingIds: string[]) {
  if (listingIds.length === 0) {
    return {} as Record<string, CrmEntry>;
  }

  try {
    const payload = await requestJson<{ data?: Record<string, CrmEntry> }>("/api/v1/crm/bulk", {
      accessToken,
      body: {
        listing_ids: listingIds,
      },
      fallbackMessage: "Failed to load CRM statuses",
      method: "POST",
    });

    return payload.data ?? {};
  } catch {
    const localEntries = loadLocalCrmEntries();
    return listingIds.reduce<Record<string, CrmEntry>>((accumulator, id) => {
      accumulator[id] = localEntries[id] ?? {
        listing_id: id,
        notes: "",
        status: null,
        updated_at: null,
      };
      return accumulator;
    }, {});
  }
}

export async function patchCrmStatus(
  accessToken: string | undefined,
  listingId: string,
  status: CrmStatus,
) {
  try {
    return await requestJson<CrmEntry>(`/api/v1/listings/${listingId}/crm/status`, {
      accessToken,
      body: { status },
      fallbackMessage: "Failed to update CRM status",
      method: "PATCH",
    });
  } catch {
    const localEntries = loadLocalCrmEntries();
    const existing = localEntries[listingId] ?? {
      listing_id: listingId,
      notes: "",
      status: null,
      updated_at: null,
    };

    return saveLocalCrmEntry({
      ...existing,
      status,
      updated_at: new Date().toISOString(),
    });
  }
}

export async function patchCrmNotes(
  accessToken: string | undefined,
  listingId: string,
  notes: string,
) {
  try {
    return await requestJson<CrmEntry>(`/api/v1/listings/${listingId}/crm/notes`, {
      accessToken,
      body: { notes },
      fallbackMessage: "Failed to save notes",
      method: "PATCH",
    });
  } catch {
    const localEntries = loadLocalCrmEntries();
    const existing = localEntries[listingId] ?? {
      listing_id: listingId,
      notes: "",
      status: null,
      updated_at: null,
    };

    return saveLocalCrmEntry({
      ...existing,
      notes,
      updated_at: new Date().toISOString(),
    });
  }
}

export async function translateText(
  accessToken: string | undefined,
  text: string,
  targetLang: string,
) {
  return requestJson<TranslatePayload>("/api/v1/translate", {
    accessToken,
    body: {
      target_lang: targetLang,
      text,
    },
    fallbackMessage: "Translation unavailable. Try again later.",
    method: "POST",
  });
}
