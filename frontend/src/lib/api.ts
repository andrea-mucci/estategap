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
export type ZonePriceDistribution = {
  zone_id: string;
  prices_eur: number[];
  listing_count: number;
};
export type ZoneComparisonItem = ZoneDetail & {
  local_currency: string;
  median_price_m2_local?: number | null;
};
export type ZoneComparisonResponse = {
  zones: ZoneComparisonItem[];
};
export type PortfolioProperty = {
  id: string;
  user_id: string;
  address: string;
  lat?: number | null;
  lng?: number | null;
  zone_id?: string | null;
  country: string;
  purchase_price: number;
  purchase_currency: string;
  purchase_price_eur: number;
  purchase_date: string;
  monthly_rental_income: number;
  monthly_rental_income_eur: number;
  area_m2?: number | null;
  property_type: "residential" | "commercial" | "industrial" | "land";
  notes?: string | null;
  estimated_value_eur?: number | null;
  estimated_at?: string | null;
  created_at: string;
  updated_at: string;
};
export type PortfolioSummary = {
  total_properties: number;
  total_invested_eur: number;
  total_current_value_eur: number;
  unrealized_gain_loss_eur: number;
  unrealized_gain_loss_pct: number;
  average_rental_yield_pct: number;
  properties_with_estimate: number;
};
export type PortfolioListResponse = {
  properties: PortfolioProperty[];
  summary: PortfolioSummary;
};
export type ScrapingPortalStat = {
  portal_id: string;
  portal_name: string;
  country: string;
  status: string;
  last_scrape_at?: string | null;
  listings_24h: number;
  success_rate: number;
  blocks_24h: number;
};
export type MLModelVersion = {
  id: string;
  country: string;
  version: string;
  mape: number;
  mae: number;
  r2: number;
  trained_at: string;
  is_active: boolean;
  train_status: "idle" | "training" | "failed";
};
export type AdminUser = {
  id: string;
  email: string;
  name?: string | null;
  role: "user" | "admin";
  subscription_tier: string;
  last_active_at?: string | null;
  created_at: string;
};
export type PortalConfig = {
  id: string;
  name: string;
  enabled: boolean;
  config: Record<string, unknown>;
};
export type CountryConfig = {
  code: string;
  name: string;
  enabled: boolean;
  portals: PortalConfig[];
};
export type SystemHealth = {
  nats: {
    subjects: Array<{
      subject: string;
      consumer_lag: number;
      message_count: number;
    }>;
  };
  database: {
    size_bytes: number;
    active_connections: number;
    max_connections: number;
    waiting_connections: number;
  };
  redis: {
    used_memory_bytes: number;
    max_memory_bytes: number;
    hit_rate: number;
    connected_clients: number;
  };
};
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
    method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
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

export async function fetchZoneDetail(accessToken: string | undefined, id: string) {
  const client = createApiClient(accessToken);
  const { data, error } = await client.GET("/api/v1/zones/{id}", {
    params: {
      path: { id },
    },
  });

  if (error || !data) {
    throw new Error(unwrapError(error, "Failed to load zone"));
  }

  return data as ZoneDetail;
}

export async function fetchZonePriceDistribution(
  accessToken: string | undefined,
  id: string,
) {
  return requestJson<ZonePriceDistribution>(`/api/v1/zones/${id}/price-distribution`, {
    accessToken,
    fallbackMessage: "Failed to load zone price distribution",
  });
}

export async function fetchZoneComparison(
  accessToken: string | undefined,
  ids: string[],
) {
  const query = new URLSearchParams({
    ids: ids.join(","),
  });

  return requestJson<ZoneComparisonResponse>(`/api/v1/zones/compare?${query.toString()}`, {
    accessToken,
    fallbackMessage: "Failed to load zone comparison",
  });
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

export async function fetchPortfolioProperties(accessToken: string | undefined) {
  return requestJson<PortfolioListResponse>("/api/v1/portfolio/properties", {
    accessToken,
    fallbackMessage: "Failed to load portfolio properties",
  });
}

export async function createPortfolioProperty(
  accessToken: string | undefined,
  body: Record<string, unknown>,
) {
  return requestJson<PortfolioProperty>("/api/v1/portfolio/properties", {
    accessToken,
    body,
    fallbackMessage: "Failed to create portfolio property",
    method: "POST",
  });
}

export async function updatePortfolioProperty(
  accessToken: string | undefined,
  id: string,
  body: Record<string, unknown>,
) {
  return requestJson<PortfolioProperty>(`/api/v1/portfolio/properties/${id}`, {
    accessToken,
    body,
    fallbackMessage: "Failed to update portfolio property",
    method: "PUT",
  });
}

export async function deletePortfolioProperty(
  accessToken: string | undefined,
  id: string,
) {
  await requestJson<void>(`/api/v1/portfolio/properties/${id}`, {
    accessToken,
    fallbackMessage: "Failed to delete portfolio property",
    method: "DELETE",
  });
}

export async function fetchAdminScrapingStats(accessToken: string | undefined) {
  return requestJson<{ portals: ScrapingPortalStat[] }>("/api/v1/admin/scraping/stats", {
    accessToken,
    fallbackMessage: "Failed to load scraping stats",
  });
}

export async function fetchAdminMLModels(accessToken: string | undefined) {
  return requestJson<{ models: MLModelVersion[] }>("/api/v1/admin/ml/models", {
    accessToken,
    fallbackMessage: "Failed to load ML models",
  });
}

export async function triggerMLRetrain(
  accessToken: string | undefined,
  country: string,
) {
  return requestJson<{ job_id: string; status: "queued" }>("/api/v1/admin/ml/retrain", {
    accessToken,
    body: { country },
    fallbackMessage: "Failed to trigger retraining",
    method: "POST",
  });
}

export async function fetchAdminUsers(
  accessToken: string | undefined,
  params: { page?: number; limit?: number; q?: string; tier?: string } = {},
) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    serializeQueryValue(key, value, query);
  }

  return requestJson<{
    users: AdminUser[];
    total: number;
    page: number;
    limit: number;
  }>(`/api/v1/admin/users${query.toString() ? `?${query.toString()}` : ""}`, {
    accessToken,
    fallbackMessage: "Failed to load users",
  });
}

export async function fetchAdminCountries(accessToken: string | undefined) {
  return requestJson<{ countries: CountryConfig[] }>("/api/v1/admin/countries", {
    accessToken,
    fallbackMessage: "Failed to load countries",
  });
}

export async function updateAdminCountry(
  accessToken: string | undefined,
  code: string,
  body: Record<string, unknown>,
) {
  return requestJson<CountryConfig>(`/api/v1/admin/countries/${code}`, {
    accessToken,
    body,
    fallbackMessage: "Failed to update country",
    method: "PUT",
  });
}

export async function fetchSystemHealth(accessToken: string | undefined) {
  return requestJson<SystemHealth>("/api/v1/admin/system/health", {
    accessToken,
    fallbackMessage: "Failed to load system health",
  });
}

export async function updateCurrentUser(
  accessToken: string | undefined,
  body: Record<string, unknown>,
) {
  return requestJson<components["schemas"]["UserProfile"]>("/api/v1/auth/me", {
    accessToken,
    body,
    fallbackMessage: "Failed to update user profile",
    method: "PATCH",
  });
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
