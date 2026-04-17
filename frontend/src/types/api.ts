export interface components {
  schemas: {
    ErrorResponse: {
      error: string;
      code?: string;
      details?: Record<string, unknown>;
      request_id?: string | null;
    };
    UserProfile: {
      id: string;
      email: string;
      display_name?: string | null;
      avatar_url?: string | null;
      subscription_tier: "free" | "basic" | "pro" | "global" | "api";
      preferred_currency: string;
      role: "user" | "admin";
      alert_limit: number;
      email_verified: boolean;
      created_at: string;
    };
    TokenPair: {
      access_token: string;
      refresh_token: string;
      expires_in: number;
      user?: components["schemas"]["UserProfile"];
    };
    PaginationEnvelope: {
      next_cursor?: string | null;
      has_more?: boolean;
    };
    ListingSummary: {
      id: string;
      source: string;
      country: string;
      city?: string | null;
      address?: string | null;
      latitude?: number | null;
      longitude?: number | null;
      asking_price?: number | null;
      asking_price_eur?: number | null;
      price_converted?: number | null;
      currency: string;
      price_per_m2_eur?: number | null;
      area_m2?: number | null;
      bedrooms?: number | null;
      bathrooms?: number | null;
      property_category?: "residential" | "commercial" | "industrial" | "land" | null;
      property_type?: string | null;
      deal_score?: number | null;
      deal_tier?: 1 | 2 | 3 | 4 | null;
      status: "active" | "delisted" | "sold";
      days_on_market?: number | null;
      photo_url?: string | null;
      first_seen_at: string;
    };
    ListingsResponse: {
      data: components["schemas"]["ListingSummary"][];
      pagination: components["schemas"]["PaginationEnvelope"];
      meta?: {
        total_count?: number;
        currency?: string;
      };
    };
    ListingGeoFeature: {
      type: "Feature";
      geometry: {
        type: "Point";
        coordinates: [number, number];
      };
      properties: {
        id: string;
        deal_tier?: 1 | 2 | 3 | 4 | null;
        deal_score?: number | null;
        asking_price_eur?: number | null;
        area_m2?: number | null;
        address?: string | null;
        photo_url?: string | null;
        city?: string | null;
        property_type?: string | null;
      };
    };
    ListingsGeoJSON: {
      type: "FeatureCollection";
      features: components["schemas"]["ListingGeoFeature"][];
    };
    ListingDetail: components["schemas"]["ListingSummary"] & {
      zone_id?: string | null;
      source_url: string;
      usable_area_m2?: number | null;
      plot_area_m2?: number | null;
      floor_number?: number | null;
      year_built?: number | null;
      condition?: string | null;
      energy_rating?: string | null;
      has_lift?: boolean | null;
      has_pool?: boolean | null;
      has_garden?: boolean | null;
      estimated_price?: number | null;
      confidence_low?: number | null;
      confidence_high?: number | null;
      shap_features?: Record<string, unknown> | null;
      model_version?: string | null;
      published_at?: string | null;
      price_history: Array<{
        old_price_eur?: number | null;
        new_price_eur?: number | null;
        change_type: string;
        recorded_at: string;
      }>;
      comparable_ids: string[];
      zone_stats?: {
        zone_id: string;
        zone_name: string;
        listing_count: number;
        median_price_m2_eur: number;
        deal_count: number;
      } | null;
      photo_urls?: string[];
    };
    DashboardSummary: {
      country: string;
      total_listings: number;
      new_today: number;
      tier1_deals_today: number;
      price_drops_7d: number;
      last_refreshed_at: string;
    };
    CountrySummary: {
      code: string;
      name: string;
      currency: string;
      listing_count: number;
      deal_count: number;
      portal_count: number;
    };
    CountryListResponse: {
      data: components["schemas"]["CountrySummary"][];
      pagination: components["schemas"]["PaginationEnvelope"];
      meta?: {
        total_count?: number;
      };
    };
    ZoneDetail: {
      id: string;
      name: string;
      name_local?: string | null;
      country: string;
      level: number;
      parent_id?: string | null;
      slug?: string | null;
      area_km2?: number | null;
      listing_count: number;
      median_price_m2_eur: number;
      deal_count: number;
      price_trend_pct?: number | null;
    };
    ZoneListResponse: {
      data: components["schemas"]["ZoneDetail"][];
      pagination: components["schemas"]["PaginationEnvelope"];
      meta?: {
        total_count?: number;
      };
    };
    ZoneAnalytics: {
      zone_id: string;
      months: Array<{
        month: string;
        listing_count: number;
        median_price_m2_eur: number;
        deal_count: number;
        avg_days_on_market: number;
      }>;
    };
    ZoneGeometry: {
      zone_id: string;
      zone_name: string;
      geometry: {
        type: "MultiPolygon";
        coordinates: number[][][][];
      };
      bbox: [number, number, number, number];
    };
    CreateCustomZoneRequest: {
      name: string;
      type: "custom";
      country: string;
      geometry: {
        type: "Polygon";
        coordinates: number[][][];
      };
    };
  };
}

type JsonResponse<T> = {
  content: {
    "application/json": T;
  };
};

export interface paths {
  "/api/v1/auth/register": {
    post: {
      requestBody: {
        content: {
          "application/json": {
            email: string;
            password: string;
            display_name?: string;
          };
        };
      };
      responses: {
        201: JsonResponse<components["schemas"]["TokenPair"]>;
        409: JsonResponse<components["schemas"]["ErrorResponse"]>;
      };
    };
  };
  "/api/v1/auth/login": {
    post: {
      requestBody: {
        content: {
          "application/json": {
            email: string;
            password: string;
          };
        };
      };
      responses: {
        200: JsonResponse<components["schemas"]["TokenPair"]>;
        401: JsonResponse<components["schemas"]["ErrorResponse"]>;
      };
    };
  };
  "/api/v1/auth/refresh": {
    post: {
      requestBody: {
        content: {
          "application/json": {
            refresh_token: string;
          };
        };
      };
      responses: {
        200: JsonResponse<components["schemas"]["TokenPair"]>;
        401: JsonResponse<components["schemas"]["ErrorResponse"]>;
      };
    };
  };
  "/api/v1/auth/logout": {
    post: {
      requestBody: {
        content: {
          "application/json": {
            refresh_token: string;
          };
        };
      };
      responses: {
        204: never;
        401: JsonResponse<components["schemas"]["ErrorResponse"]>;
      };
    };
  };
  "/api/v1/auth/me": {
    get: {
      responses: {
        200: JsonResponse<components["schemas"]["UserProfile"]>;
        401: JsonResponse<components["schemas"]["ErrorResponse"]>;
      };
    };
  };
  "/api/v1/listings": {
    get: {
      parameters: {
        query: {
          country: string;
          city?: string;
          zone_id?: string;
          property_type?: string;
          property_category?: "residential" | "commercial" | "industrial" | "land";
          min_price_eur?: number;
          max_price_eur?: number;
          min_area_m2?: number;
          max_area_m2?: number;
          min_bedrooms?: number;
          min_bathrooms?: number;
          deal_tier?: 1 | 2 | 3 | 4;
          status?: "active" | "delisted" | "sold";
          sort_by?: "recency" | "deal_score" | "price" | "price_m2" | "days_on_market";
          sort_dir?: "asc" | "desc";
          currency?: string;
          bounds?: string;
          format?: "json" | "geojson";
          cursor?: string;
          limit?: number;
        };
      };
      responses: {
        200: JsonResponse<components["schemas"]["ListingsResponse"] | components["schemas"]["ListingsGeoJSON"]>;
        401: JsonResponse<components["schemas"]["ErrorResponse"]>;
      };
    };
  };
  "/api/v1/listings/{id}": {
    get: {
      parameters: {
        path: {
          id: string;
        };
      };
      responses: {
        200: JsonResponse<components["schemas"]["ListingDetail"]>;
        401: JsonResponse<components["schemas"]["ErrorResponse"]>;
        404: JsonResponse<components["schemas"]["ErrorResponse"]>;
      };
    };
  };
  "/api/v1/dashboard/summary": {
    get: {
      parameters: {
        query: {
          country: string;
        };
      };
      responses: {
        200: JsonResponse<components["schemas"]["DashboardSummary"]>;
        400: JsonResponse<components["schemas"]["ErrorResponse"]>;
        401: JsonResponse<components["schemas"]["ErrorResponse"]>;
        403: JsonResponse<components["schemas"]["ErrorResponse"]>;
      };
    };
  };
  "/api/v1/countries": {
    get: {
      responses: {
        200: JsonResponse<components["schemas"]["CountryListResponse"]>;
        401: JsonResponse<components["schemas"]["ErrorResponse"]>;
      };
    };
  };
  "/api/v1/zones": {
    get: {
      parameters: {
        query: {
          country: string;
          level?: number;
          parent_id?: string;
          cursor?: string;
          limit?: number;
        };
      };
      responses: {
        200: JsonResponse<components["schemas"]["ZoneListResponse"]>;
        401: JsonResponse<components["schemas"]["ErrorResponse"]>;
      };
    };
    post: {
      requestBody: {
        content: {
          "application/json": components["schemas"]["CreateCustomZoneRequest"];
        };
      };
      responses: {
        201: JsonResponse<components["schemas"]["ZoneDetail"]>;
        400: JsonResponse<components["schemas"]["ErrorResponse"]>;
        401: JsonResponse<components["schemas"]["ErrorResponse"]>;
        422: JsonResponse<components["schemas"]["ErrorResponse"]>;
        429: JsonResponse<components["schemas"]["ErrorResponse"]>;
      };
    };
  };
  "/api/v1/zones/{id}/analytics": {
    get: {
      parameters: {
        path: {
          id: string;
        };
      };
      responses: {
        200: JsonResponse<components["schemas"]["ZoneAnalytics"]>;
        401: JsonResponse<components["schemas"]["ErrorResponse"]>;
        404: JsonResponse<components["schemas"]["ErrorResponse"]>;
      };
    };
  };
  "/api/v1/zones/{id}/geometry": {
    get: {
      parameters: {
        path: {
          id: string;
        };
      };
      responses: {
        200: JsonResponse<components["schemas"]["ZoneGeometry"]>;
        401: JsonResponse<components["schemas"]["ErrorResponse"]>;
        404: JsonResponse<components["schemas"]["ErrorResponse"]>;
      };
    };
  };
}
