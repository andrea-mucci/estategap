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
    ListingSummary: {
      id: string;
      source: string;
      country: string;
      city?: string | null;
      address?: string | null;
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
    ListingsPage: {
      items: components["schemas"]["ListingSummary"][];
      total: number;
      cursor: string | null;
    };
    ListingDetail: components["schemas"]["ListingSummary"] & {
      description?: string | null;
      photo_urls?: string[];
      estimated_price_eur?: number | null;
      confidence_low_eur?: number | null;
      confidence_high_eur?: number | null;
      shap_features?: Array<{
        feature: string;
        impact: number;
      }>;
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
          cursor?: string;
          limit?: number;
        };
      };
      responses: {
        200: JsonResponse<components["schemas"]["ListingsPage"]>;
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
}
