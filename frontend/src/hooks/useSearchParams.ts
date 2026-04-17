"use client";

import { useMemo } from "react";
import {
  parseAsArrayOf,
  parseAsInteger,
  parseAsString,
  parseAsStringLiteral,
  useQueryStates,
} from "nuqs";

import {
  DEFAULT_SEARCH_PARAMS,
  getActiveFilterCount,
  type ListingSearchParams,
  type ListingSortBy,
  type ListingSortDir,
  type ListingStatusFilter,
  type PropertyCategory,
} from "@/lib/listing-search";

const propertyCategoryParser = parseAsStringLiteral([
  "residential",
  "commercial",
  "industrial",
  "land",
] as const);

const sortByParser = parseAsStringLiteral([
  "deal_score",
  "price",
  "price_m2",
  "recency",
  "days_on_market",
] as const);

const sortDirParser = parseAsStringLiteral(["asc", "desc"] as const);

const statusValueParser = parseAsStringLiteral([
  "active",
  "delisted",
  "price_changed",
  "sold",
] as const);

const searchParamParsers = {
  country: parseAsString.withDefault(DEFAULT_SEARCH_PARAMS.country),
  city: parseAsString,
  zone_id: parseAsString,
  property_category: propertyCategoryParser,
  property_type: parseAsString,
  min_price_eur: parseAsInteger,
  max_price_eur: parseAsInteger,
  min_area_m2: parseAsInteger,
  max_area_m2: parseAsInteger,
  min_bedrooms: parseAsInteger,
  deal_tier: parseAsArrayOf(parseAsInteger),
  status: parseAsArrayOf(statusValueParser),
  source_portal: parseAsArrayOf(parseAsString),
  sort_by: sortByParser.withDefault(DEFAULT_SEARCH_PARAMS.sort_by),
  sort_dir: sortDirParser.withDefault(DEFAULT_SEARCH_PARAMS.sort_dir),
};

const resetParams = {
  city: null,
  deal_tier: [],
  max_area_m2: null,
  max_price_eur: null,
  min_area_m2: null,
  min_bedrooms: null,
  min_price_eur: null,
  property_category: null,
  property_type: null,
  sort_by: DEFAULT_SEARCH_PARAMS.sort_by,
  sort_dir: DEFAULT_SEARCH_PARAMS.sort_dir,
  source_portal: [],
  status: [],
  zone_id: null,
} as const;

export { type ListingSearchParams } from "@/lib/listing-search";

export function useListingSearchParams() {
  const [params, setParams] = useQueryStates(searchParamParsers, {
    clearOnDefault: true,
    history: "replace",
    shallow: true,
  });

  const normalizedParams = useMemo<ListingSearchParams>(
    () => ({
      country: params.country ?? DEFAULT_SEARCH_PARAMS.country,
      city: params.city ?? null,
      zone_id: params.zone_id ?? null,
      property_category: (params.property_category as PropertyCategory | null) ?? null,
      property_type: params.property_type ?? null,
      min_price_eur: params.min_price_eur ?? null,
      max_price_eur: params.max_price_eur ?? null,
      min_area_m2: params.min_area_m2 ?? null,
      max_area_m2: params.max_area_m2 ?? null,
      min_bedrooms: params.min_bedrooms ?? null,
      deal_tier: params.deal_tier ?? [],
      status: (params.status as ListingStatusFilter[] | null) ?? [],
      source_portal: params.source_portal ?? [],
      sort_by: (params.sort_by as ListingSortBy | null) ?? DEFAULT_SEARCH_PARAMS.sort_by,
      sort_dir: (params.sort_dir as ListingSortDir | null) ?? DEFAULT_SEARCH_PARAMS.sort_dir,
    }),
    [params],
  );

  const activeCount = useMemo(
    () => getActiveFilterCount(normalizedParams),
    [normalizedParams],
  );

  return {
    activeCount,
    params: normalizedParams,
    reset: () => setParams(resetParams),
    setParams,
  };
}

