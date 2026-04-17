import type {
  CarouselItem,
  ChatMessage,
  ChipOption,
  SearchCriteria,
  SearchResultsPayload,
} from "@/stores/chatStore";
import { useChatStore } from "@/stores/chatStore";
import { useNotificationStore } from "@/stores/notificationStore";

export interface TextChunkPayload {
  text: string;
  conversation_id: string;
  is_final: boolean;
}

export interface ChipsPayload {
  options: ChipOption[];
}

export interface ImageCarouselPayload {
  listings: CarouselItem[];
}

export interface CriteriaSummaryPayload {
  conversation_id: string;
  criteria: Record<string, unknown>;
  ready_to_search: boolean;
}

export interface DealAlertPayload {
  event_id: string;
  listing_id: string;
  title: string;
  address: string;
  price_eur: number;
  area_m2: number;
  deal_score: number;
  deal_tier: number;
  photo_url?: string;
  analysis_url?: string;
  rule_name: string;
  triggered_at: string;
}

export interface ErrorPayload {
  code: string;
  message: string;
}

export interface WsEnvelope {
  type:
    | "text_chunk"
    | "chips"
    | "image_carousel"
    | "criteria_summary"
    | "search_results"
    | "deal_alert"
    | "error"
    | "pong";
  session_id?: string;
  payload: unknown;
}

type Handler = (message: WsEnvelope) => void;

function createMessage(message: Omit<ChatMessage, "id" | "timestamp">): ChatMessage {
  return {
    id: `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    timestamp: Date.now(),
    ...message,
  };
}

function buildWsUrl(jwt: string) {
  const baseUrl = (process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:9090").replace(
    /\/$/,
    "",
  );
  return `${baseUrl}/ws/chat?token=${encodeURIComponent(jwt)}`;
}

export class WebSocketManager {
  private socket: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private handlers = new Set<Handler>();
  private backoffMs = 1000;
  private token: string | null = null;
  private shouldReconnect = false;

  connect(jwt: string) {
    if (this.socket && this.token === jwt && this.socket.readyState <= WebSocket.OPEN) {
      return;
    }

    this.token = jwt;
    this.shouldReconnect = true;
    this.clearReconnect();
    this.clearHeartbeat();
    this.socket?.close();

    useChatStore.getState().setWsStatus("connecting");

    const socket = new WebSocket(buildWsUrl(jwt));
    this.socket = socket;

    socket.onopen = () => {
      this.backoffMs = 1000;
      useChatStore.getState().setWsStatus("connected");
      this.startHeartbeat();
    };

    socket.onmessage = (event) => {
      try {
        const envelope = JSON.parse(event.data) as WsEnvelope;
        this.routeMessage(envelope);
        this.handlers.forEach((handler) => handler(envelope));
      } catch {
        useChatStore.getState().addMessage(
          createMessage({
            role: "system",
            type: "error",
            content: "Failed to parse real-time payload.",
          }),
        );
      }
    };

    socket.onerror = () => {
      useChatStore.getState().setWsStatus("error");
    };

    socket.onclose = () => {
      this.clearHeartbeat();
      if (this.shouldReconnect && this.token) {
        useChatStore.getState().setWsStatus("disconnected");
        this.scheduleReconnect();
        return;
      }

      useChatStore.getState().setWsStatus("disconnected");
    };
  }

  disconnect() {
    this.shouldReconnect = false;
    this.clearReconnect();
    this.clearHeartbeat();

    if (this.socket) {
      const socket = this.socket;
      this.socket = null;
      socket.close();
    }
  }

  send(message: object) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket is not connected");
    }

    this.socket.send(JSON.stringify(message));
  }

  onMessage(handler: Handler) {
    this.handlers.add(handler);
    return () => {
      this.handlers.delete(handler);
    };
  }

  private startHeartbeat() {
    this.clearHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.socket?.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: "ping", payload: {} }));
      }
    }, 25_000);
  }

  private scheduleReconnect() {
    if (this.reconnectTimer || !this.token) {
      return;
    }

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      const token = this.token;
      if (token) {
        this.backoffMs = Math.min(this.backoffMs * 2, 30_000);
        this.connect(token);
      }
    }, this.backoffMs);
  }

  private clearReconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private clearHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private routeMessage(envelope: WsEnvelope) {
    const chatStore = useChatStore.getState();
    const notificationStore = useNotificationStore.getState();

    if (envelope.session_id && !chatStore.sessionId) {
      chatStore.setSessionId(envelope.session_id);
    }

    switch (envelope.type) {
      case "text_chunk": {
        const payload = envelope.payload as TextChunkPayload;
        chatStore.appendChunk(payload.conversation_id, payload.text, payload.is_final);
        break;
      }
      case "chips": {
        const payload = envelope.payload as ChipsPayload;
        chatStore.addMessage(
          createMessage({
            role: "assistant",
            type: "chips",
            content: "",
            chips: payload.options,
          }),
        );
        break;
      }
      case "image_carousel": {
        const payload = envelope.payload as ImageCarouselPayload;
        chatStore.addMessage(
          createMessage({
            role: "assistant",
            type: "carousel",
            content: "",
            carousel: payload.listings,
          }),
        );
        break;
      }
      case "criteria_summary": {
        const payload = envelope.payload as CriteriaSummaryPayload;
        const criteria: SearchCriteria = {
          conversationId: payload.conversation_id,
          criteria: payload.criteria,
          readyToSearch: payload.ready_to_search,
        };
        chatStore.setCriteria(criteria);
        chatStore.addMessage(
          createMessage({
            role: "assistant",
            type: "criteria",
            content: "",
            criteria,
          }),
        );
        break;
      }
      case "search_results": {
        const payload = envelope.payload as SearchResultsPayload;
        chatStore.addMessage(
          createMessage({
            role: "assistant",
            type: "results",
            content: "",
            results: payload,
          }),
        );
        break;
      }
      case "deal_alert": {
        const payload = envelope.payload as DealAlertPayload;
        notificationStore.addAlert({
          eventId: payload.event_id,
          listingId: payload.listing_id,
          title: payload.title,
          address: payload.address,
          priceEur: payload.price_eur,
          areaM2: payload.area_m2,
          dealScore: payload.deal_score,
          dealTier: payload.deal_tier,
          photoUrl: payload.photo_url,
          analysisUrl: payload.analysis_url,
          ruleName: payload.rule_name,
          triggeredAt: payload.triggered_at,
          read: false,
        });
        notificationStore.pushToast({
          type: "alert",
          title: payload.title,
          description: `${payload.address} · score ${payload.deal_score}`,
          durationMs: 7000,
        });
        break;
      }
      case "error": {
        const payload = envelope.payload as ErrorPayload;
        chatStore.addMessage(
          createMessage({
            role: "system",
            type: "error",
            content: payload.message,
          }),
        );
        break;
      }
      case "pong":
      default:
        break;
    }
  }
}
