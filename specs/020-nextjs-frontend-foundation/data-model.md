# Data Model: Next.js Frontend Foundation

**Date**: 2026-04-17 | **Branch**: `020-nextjs-frontend-foundation`

> All types below are TypeScript interfaces used by the frontend stores, components, and WS client.
> API response types are auto-generated from `services/api-gateway/openapi.yaml` into `src/types/api.ts`.
> Only client-side state types (Zustand stores, WS protocol) are defined manually here.

---

## 1. Extended NextAuth Session

```ts
// src/types/next-auth.d.ts
import "next-auth";

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      email: string;
      name: string | null;
      image: string | null;
      subscriptionTier: "free" | "pro" | "enterprise";
      role: "user" | "admin";
    };
    accessToken: string;          // backend JWT for API calls
    accessTokenExpires: number;   // Unix epoch ms
  }

  interface JWT {
    accessToken: string;
    accessTokenExpires: number;
    refreshToken: string;
    subscriptionTier: "free" | "pro" | "enterprise";
    role: "user" | "admin";
    error?: "RefreshTokenExpired";
  }
}
```

---

## 2. Chat Store Types

```ts
// src/stores/chatStore.ts

export type MessageRole = "user" | "assistant" | "system";
export type WsStatus = "disconnected" | "connecting" | "connected" | "error";

export interface ChatMessage {
  id: string;                          // client-generated uuid
  role: MessageRole;
  type: "text" | "chips" | "carousel" | "criteria" | "results" | "error";
  content: string;                     // text content (for text/error types)
  chips?: ChipOption[];
  carousel?: CarouselItem[];
  criteria?: SearchCriteria;
  results?: SearchResultsPayload;
  timestamp: number;                   // Date.now()
  isStreaming?: boolean;               // true while text_chunk is_final=false
}

export interface SearchCriteria {
  conversationId: string;
  criteria: Record<string, unknown>;   // raw criteria object from server
  readyToSearch: boolean;
}

export interface ChatStore {
  sessionId: string | null;
  messages: ChatMessage[];
  criteria: SearchCriteria | null;
  wsStatus: WsStatus;
  setSessionId: (id: string) => void;
  addMessage: (msg: ChatMessage) => void;
  appendChunk: (conversationId: string, chunk: string, isFinal: boolean) => void;
  setCriteria: (c: SearchCriteria) => void;
  setWsStatus: (s: WsStatus) => void;
  reset: () => void;
}
```

---

## 3. Notification Store Types

```ts
// src/stores/notificationStore.ts

export interface DealAlert {
  eventId: string;
  listingId: string;
  title: string;
  address: string;
  priceEur: number;
  areaM2: number;
  dealScore: number;
  dealTier: number;
  photoUrl?: string;
  analysisUrl?: string;
  ruleName: string;
  triggeredAt: string;               // ISO 8601
  read: boolean;
}

export interface Toast {
  id: string;
  type: "alert" | "success" | "error" | "info";
  title: string;
  description?: string;
  durationMs: number;
}

export interface NotificationStore {
  alerts: DealAlert[];
  toastQueue: Toast[];
  unreadCount: number;
  addAlert: (a: DealAlert) => void;
  markRead: (eventId: string) => void;
  markAllRead: () => void;
  pushToast: (t: Omit<Toast, "id">) => void;
  dismissToast: (id: string) => void;
}
```

---

## 4. UI Store Types

```ts
// src/stores/uiStore.ts

export interface UIStore {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (v: boolean) => void;
}
```

---

## 5. WebSocket Protocol Types

```ts
// src/lib/ws.ts (inline types)

/** Server-sent envelope (matches ws-server/internal/protocol/messages.go) */
export interface WsEnvelope {
  type: WsMessageType;
  session_id?: string;
  payload: unknown;
}

export type WsMessageType =
  | "text_chunk"
  | "chips"
  | "image_carousel"
  | "criteria_summary"
  | "search_results"
  | "deal_alert"
  | "error"
  | "pong";

export type WsClientMessageType =
  | "chat_message"
  | "image_feedback"
  | "criteria_confirm"
  | "ping";

// Payload shapes (mirror Go structs in messages.go)
export interface TextChunkPayload   { text: string; conversation_id: string; is_final: boolean; }
export interface ChipsPayload       { options: ChipOption[]; }
export interface ChipOption         { label: string; value: string; }
export interface ImageCarouselPayload { listings: CarouselItem[]; }
export interface CarouselItem       { listing_id: string; title: string; price_eur: number; area_m2: number; city: string; photo_urls: string[]; deal_score?: number; }
export interface CriteriaSummaryPayload { conversation_id: string; criteria: unknown; ready_to_search: boolean; }
export interface SearchResultsPayload   { conversation_id: string; total_count: number; listings: SearchListing[]; }
export interface SearchListing          { listing_id: string; title?: string; price_eur?: number; area_m2?: number; bedrooms?: number; city?: string; deal_score?: number; deal_tier?: number; image_url?: string; analysis_url?: string; }
export interface DealAlertPayload       { event_id: string; listing_id: string; title: string; address: string; price_eur: number; area_m2: number; deal_score: number; deal_tier: number; photo_url?: string; analysis_url?: string; rule_name: string; triggered_at: string; }
export interface ErrorPayload           { code: string; message: string; }

// Client → Server payloads
export interface ChatMessagePayload    { user_message: string; country_code?: string; }
export interface ImageFeedbackPayload  { listing_id: string; action: string; }
export interface CriteriaConfirmPayload { confirmed: boolean; notes?: string; }
```

---

## 6. i18n Message File Schema

All `messages/{locale}.json` files follow this structure (English as canonical reference):

```ts
interface Messages {
  nav: {
    home: string; search: string; dashboard: string;
    zones: string; alerts: string; portfolio: string; admin: string;
  };
  auth: {
    login: string; register: string; logout: string;
    email: string; password: string; name: string;
    loginWithGoogle: string; alreadyHaveAccount: string;
    dontHaveAccount: string; forgotPassword: string;
    loginError: string; registerError: string;
  };
  chat: {
    placeholder: string; send: string; thinking: string;
    newSession: string; chooseOption: string;
  };
  common: {
    loading: string; error: string; retry: string;
    save: string; cancel: string; confirm: string; close: string;
    noResults: string;
  };
  listing: {
    price: string; area: string; bedrooms: string;
    dealScore: string; viewDetails: string;
  };
  alerts: {
    newDeal: string; dealScore: string; viewListing: string;
    markRead: string; markAllRead: string;
  };
  meta: {
    appName: string; tagline: string;
  };
}
```

---

## 7. Entity Relationships

```
NextAuth Session
  └─ user.id → API Gateway /users/me (UserProfile)
  └─ accessToken → all API calls (Authorization: Bearer)
  └─ accessToken → WebSocket connect (?token=)

ChatStore
  └─ sessionId → WsEnvelope.session_id
  └─ messages[] ← WebSocket inbound (text_chunk, chips, carousel, etc.)
  └─ criteria ← criteria_summary payload

NotificationStore
  └─ alerts[] ← deal_alert WebSocket messages
  └─ toastQueue[] ← derived from incoming alerts

UIStore
  └─ sidebarOpen → MainLayout (sidebar CSS class)

API types (auto-generated)
  └─ src/types/api.ts ← openapi-typescript ← services/api-gateway/openapi.yaml
  └─ consumed by all TanStack Query hooks via openapi-fetch client
```
