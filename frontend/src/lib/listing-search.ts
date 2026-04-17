import type { ListingDetail } from "@/lib/api";

export type PropertyCategory =
  | "residential"
  | "commercial"
  | "industrial"
  | "land";

export type ListingStatusFilter =
  | "active"
  | "delisted"
  | "price_changed"
  | "sold";

export type ListingSortBy =
  | "deal_score"
  | "price"
  | "price_m2"
  | "recency"
  | "days_on_market";

export type ListingSortDir = "asc" | "desc";

export type SearchViewMode = "grid" | "list";

export type DeepLTargetLanguage =
  | "EN-GB"
  | "ES"
  | "FR"
  | "DE"
  | "IT"
  | "PT-PT"
  | "NL"
  | "PL"
  | "SV"
  | "EL";

type TranslationValue = Date | number | string | boolean | null | undefined;
type TranslationFn = (key: string, values?: Record<string, TranslationValue>) => string;

export type PointOfInterest = {
  lat: number;
  lng: number;
  name: string;
  type: "metro" | "school" | "park";
};

export type ExtendedListingDetail = ListingDetail & {
  description?: string | null;
  description_language?: string | null;
  external_title?: string | null;
  source_portal?: string | null;
  zone_name?: string | null;
  zone_stats?: ListingDetail["zone_stats"] & {
    pois?: PointOfInterest[] | null;
    price_trend_pct?: number | null;
  };
};

export type ListingSearchParams = {
  country: string;
  city?: string | null;
  zone_id?: string | null;
  property_category?: PropertyCategory | null;
  property_type?: string | null;
  min_price_eur?: number | null;
  max_price_eur?: number | null;
  min_area_m2?: number | null;
  max_area_m2?: number | null;
  min_bedrooms?: number | null;
  deal_tier?: number[];
  status?: ListingStatusFilter[];
  source_portal?: string[];
  sort_by: ListingSortBy;
  sort_dir: ListingSortDir;
};

export const DEFAULT_SEARCH_PARAMS: ListingSearchParams = {
  country: "ES",
  sort_by: "deal_score",
  sort_dir: "desc",
  deal_tier: [],
  source_portal: [],
  status: [],
};

export const PROPERTY_CATEGORY_OPTIONS: Array<{
  label: string;
  value: PropertyCategory;
}> = [
  { label: "Residential", value: "residential" },
  { label: "Commercial", value: "commercial" },
  { label: "Industrial", value: "industrial" },
  { label: "Land", value: "land" },
];

export const PROPERTY_TYPE_OPTIONS: Record<PropertyCategory, string[]> = {
  residential: ["apartment", "penthouse", "house", "villa", "duplex", "studio"],
  commercial: ["office", "retail", "hotel", "mixed_use"],
  industrial: ["warehouse", "factory", "logistics", "industrial_land"],
  land: ["urban_plot", "rural_plot", "development_site"],
};

export const SORT_OPTIONS: Array<{
  label: string;
  sortBy: ListingSortBy;
  sortDir: ListingSortDir;
  value: string;
}> = [
  { label: "Deal Score", sortBy: "deal_score", sortDir: "desc", value: "deal_score:desc" },
  { label: "Price ↑", sortBy: "price", sortDir: "asc", value: "price:asc" },
  { label: "Price ↓", sortBy: "price", sortDir: "desc", value: "price:desc" },
  { label: "Price/m² ↑", sortBy: "price_m2", sortDir: "asc", value: "price_m2:asc" },
  { label: "Newest", sortBy: "recency", sortDir: "desc", value: "recency:desc" },
  {
    label: "Days on Market",
    sortBy: "days_on_market",
    sortDir: "asc",
    value: "days_on_market:asc",
  },
];

export const DEAL_TIER_OPTIONS = [
  { label: "T1", description: "Great", tone: "bg-emerald-50 text-emerald-700", value: 1 },
  { label: "T2", description: "Good", tone: "bg-sky-50 text-sky-700", value: 2 },
  { label: "T3", description: "Fair", tone: "bg-slate-100 text-slate-700", value: 3 },
  { label: "T4", description: "Weak", tone: "bg-rose-50 text-rose-700", value: 4 },
] as const;

export const STATUS_OPTIONS: Array<{
  label: string;
  value: ListingStatusFilter;
}> = [
  { label: "Active", value: "active" },
  { label: "Delisted", value: "delisted" },
  { label: "Price Changed", value: "price_changed" },
];

export const DEFAULT_PORTAL_OPTIONS = [
  "idealista",
  "fotocasa",
  "habitaclia",
  "rightmove",
  "immowelt",
];

export const CRM_STATUS_ORDER = [
  "favorite",
  "contacted",
  "visited",
  "offer",
  "discard",
] as const;

export const CRM_STATUS_LABELS: Record<
  NonNullable<typeof CRM_STATUS_ORDER[number]>,
  string
> = {
  favorite: "Favorite",
  contacted: "Contacted",
  visited: "Visited",
  offer: "Offer",
  discard: "Discard",
};

export const CRM_STATUS_TONES: Record<
  NonNullable<typeof CRM_STATUS_ORDER[number]>,
  string
> = {
  favorite: "bg-rose-50 text-rose-700 border-rose-200",
  contacted: "bg-sky-50 text-sky-700 border-sky-200",
  visited: "bg-emerald-50 text-emerald-700 border-emerald-200",
  offer: "bg-amber-50 text-amber-700 border-amber-200",
  discard: "bg-slate-100 text-slate-700 border-slate-200",
};

export const LOCALE_TO_DEEPL: Record<string, DeepLTargetLanguage> = {
  en: "EN-GB",
  es: "ES",
  fr: "FR",
  de: "DE",
  it: "IT",
  pt: "PT-PT",
  nl: "NL",
  pl: "PL",
  sv: "SV",
  el: "EL",
};

export const SHAP_LABELS: Record<string, string> = {
  area_m2: "Area",
  price_per_m2: "Price / m²",
  price_per_m2_eur: "Price / m²",
  distance_metro_m: "Metro distance",
  distance_school_m: "School distance",
  distance_park_m: "Park distance",
  floor: "Floor",
  floor_number: "Floor",
  year_built: "Year built",
  bedrooms: "Bedrooms",
  bathrooms: "Bathrooms",
  zone_median_price: "Zone median price",
  deal_score: "Deal score",
};

const PROPERTY_TYPE_LABEL_KEYS: Record<string, string> = {
  apartment: "apartment",
  penthouse: "penthouse",
  house: "house",
  villa: "villa",
  duplex: "duplex",
  studio: "studio",
  office: "office",
  retail: "retail",
  hotel: "hotel",
  mixed_use: "mixedUse",
  warehouse: "warehouse",
  factory: "factory",
  logistics: "logistics",
  industrial_land: "industrialLand",
  urban_plot: "urbanPlot",
  rural_plot: "ruralPlot",
  development_site: "developmentSite",
};

const SORT_OPTION_LABEL_KEYS: Record<string, string> = {
  "deal_score:desc": "dealScore",
  "price:asc": "priceAsc",
  "price:desc": "priceDesc",
  "price_m2:asc": "pricePerSquareMeterAsc",
  "recency:desc": "newest",
  "days_on_market:asc": "daysOnMarket",
};

const SHAP_LABEL_KEYS: Record<string, string> = {
  area_m2: "area",
  price_per_m2: "pricePerSquareMeter",
  price_per_m2_eur: "pricePerSquareMeter",
  distance_metro_m: "metroDistance",
  distance_school_m: "schoolDistance",
  distance_park_m: "parkDistance",
  floor: "floor",
  floor_number: "floor",
  year_built: "yearBuilt",
  bedrooms: "bedrooms",
  bathrooms: "bathrooms",
  zone_median_price: "zoneMedianPrice",
  deal_score: "dealScore",
};

export function flattenInfiniteItems<T>(pages?: Array<{ items: T[] }>) {
  return (pages ?? []).flatMap((page) => page.items);
}

export function getActiveFilterCount(params: ListingSearchParams) {
  let count = 0;

  for (const [key, value] of Object.entries(params)) {
    if (key === "country" && value === DEFAULT_SEARCH_PARAMS.country) {
      continue;
    }

    if (key === "sort_by" && value === DEFAULT_SEARCH_PARAMS.sort_by) {
      continue;
    }

    if (key === "sort_dir" && value === DEFAULT_SEARCH_PARAMS.sort_dir) {
      continue;
    }

    if (Array.isArray(value)) {
      count += value.length > 0 ? 1 : 0;
      continue;
    }

    if (value !== null && value !== undefined && value !== "") {
      count += 1;
    }
  }

  return count;
}

export function getDealTierMeta(tier?: number | null) {
  return DEAL_TIER_OPTIONS.find((option) => option.value === tier) ?? DEAL_TIER_OPTIONS[2];
}

export function getListingHeadline(listing: {
  address?: string | null;
  city?: string | null;
  external_title?: string | null;
  id: string;
}) {
  return listing.external_title ?? listing.address ?? listing.city ?? listing.id;
}

export function getListingImage(listing: {
  photo_urls?: string[] | null;
  photo_url?: string | null;
}) {
  return listing.photo_urls?.[0] ?? listing.photo_url ?? null;
}

export function getListingLocation(listing: {
  city?: string | null;
  address?: string | null;
  zone_name?: string | null;
}) {
  return [listing.city, listing.zone_name, listing.address].filter(Boolean).join(" · ");
}

export function getPriceHistoryPoints(priceHistory: ListingDetail["price_history"]) {
  return priceHistory
    .map((entry) => ({
      date: entry.recorded_at,
      price: entry.new_price_eur ?? entry.old_price_eur ?? null,
    }))
    .filter((entry): entry is { date: string; price: number } => entry.price != null);
}

export function humanizeToken(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function getPropertyCategoryLabel(
  t: TranslationFn,
  value: PropertyCategory,
) {
  return t(`categoryLabels.${value}`);
}

export function getPropertyTypeLabel(t: TranslationFn, value: string) {
  const labelKey = PROPERTY_TYPE_LABEL_KEYS[value];
  return labelKey ? t(`propertyTypeLabels.${labelKey}`) : humanizeToken(value);
}

export function getSortOptionLabel(t: TranslationFn, value: string) {
  const labelKey = SORT_OPTION_LABEL_KEYS[value];
  return labelKey ? t(`sortOptions.${labelKey}`) : humanizeToken(value);
}

export function getDealTierDescription(t: TranslationFn, value?: number | null) {
  if (!value) {
    return "";
  }

  return t(`dealTierDescriptions.${value}`);
}

export function getStatusLabel(t: TranslationFn, value: ListingStatusFilter) {
  return t(`statusLabels.${value}`);
}

export function getCrmStatusLabel(
  t: TranslationFn,
  value: (typeof CRM_STATUS_ORDER)[number],
) {
  return t(`crmStatus.${value}`);
}

export function getShapLabel(t: TranslationFn, value: string) {
  const labelKey = SHAP_LABEL_KEYS[value];
  return labelKey ? t(`shapLabels.${labelKey}`) : humanizeToken(value);
}
