import { create } from "zustand";
import { immer } from "zustand/middleware/immer";

export type MessageRole = "user" | "assistant" | "system";
export type WsStatus = "disconnected" | "connecting" | "connected" | "error";

export interface ChipOption {
  label: string;
  value: string;
}

export interface CarouselItem {
  listing_id: string;
  title: string;
  price_eur: number;
  area_m2: number;
  city: string;
  photo_urls: string[];
  deal_score?: number;
}

export interface SearchListing {
  listing_id: string;
  title?: string;
  price_eur?: number;
  area_m2?: number;
  bedrooms?: number;
  city?: string;
  deal_score?: number;
  deal_tier?: number;
  image_url?: string;
  analysis_url?: string;
}

export interface SearchCriteria {
  conversationId: string;
  criteria: Record<string, unknown>;
  readyToSearch: boolean;
}

export interface SearchResultsPayload {
  conversation_id: string;
  total_count: number;
  listings: SearchListing[];
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  type: "text" | "chips" | "carousel" | "criteria" | "results" | "error";
  content: string;
  chips?: ChipOption[];
  carousel?: CarouselItem[];
  criteria?: SearchCriteria;
  results?: SearchResultsPayload;
  timestamp: number;
  isStreaming?: boolean;
}

export interface ChatStore {
  sessionId: string | null;
  messages: ChatMessage[];
  criteria: SearchCriteria | null;
  wsStatus: WsStatus;
  setSessionId: (id: string) => void;
  addMessage: (message: ChatMessage) => void;
  appendChunk: (conversationId: string, chunk: string, isFinal: boolean) => void;
  setCriteria: (criteria: SearchCriteria) => void;
  setWsStatus: (status: WsStatus) => void;
  reset: () => void;
}

const initialState = {
  sessionId: null,
  messages: [],
  criteria: null,
  wsStatus: "disconnected" as WsStatus,
};

function createMessageId(seed?: string) {
  return seed ?? `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export const useChatStore = create<ChatStore>()(
  immer((set) => ({
    ...initialState,
    setSessionId: (id) =>
      set((state) => {
        state.sessionId = id;
      }),
    addMessage: (message) =>
      set((state) => {
        state.messages.push({
          ...message,
          id: message.id || createMessageId(),
          timestamp: message.timestamp || Date.now(),
        });
      }),
    appendChunk: (conversationId, chunk, isFinal) =>
      set((state) => {
        if (!state.sessionId) {
          state.sessionId = conversationId;
        }

        const streamingMessage = [...state.messages]
          .reverse()
          .find(
            (message) =>
              message.type === "text" &&
              message.role === "assistant" &&
              message.id === conversationId,
          );

        if (streamingMessage) {
          streamingMessage.content += chunk;
          streamingMessage.isStreaming = !isFinal;
          streamingMessage.timestamp = Date.now();
          return;
        }

        state.messages.push({
          id: conversationId || createMessageId(),
          role: "assistant",
          type: "text",
          content: chunk,
          timestamp: Date.now(),
          isStreaming: !isFinal,
        });
      }),
    setCriteria: (criteria) =>
      set((state) => {
        state.criteria = criteria;
      }),
    setWsStatus: (status) =>
      set((state) => {
        state.wsStatus = status;
      }),
    reset: () =>
      set(() => ({
        ...initialState,
        messages: [],
      })),
  })),
);
