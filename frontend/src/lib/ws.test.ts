import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useNotificationStore } from "@/stores/notificationStore";
import { useChatStore } from "@/stores/chatStore";

import { WebSocketManager } from "./ws";

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances: MockWebSocket[] = [];

  readyState = MockWebSocket.CONNECTING;
  sent: string[] = [];
  url: string;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({} as CloseEvent);
  }

  emitOpen() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  emitClose() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({} as CloseEvent);
  }

  emitMessage(payload: unknown) {
    this.onmessage?.({
      data: JSON.stringify(payload),
    } as MessageEvent);
  }
}

describe("WebSocketManager", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    process.env.NEXT_PUBLIC_WS_URL = "ws://localhost:9090";
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
    useChatStore.setState({
      sessionId: null,
      messages: [],
      criteria: null,
      wsStatus: "disconnected",
    });
    useNotificationStore.setState({
      alerts: [],
      toastQueue: [],
      unreadCount: 0,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("connects with the expected websocket URL", () => {
    const manager = new WebSocketManager();
    manager.connect("token-123");

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toBe(
      "ws://localhost:9090/ws/chat?token=token-123",
    );
  });

  it("reconnects with backoff after close", () => {
    const manager = new WebSocketManager();
    manager.connect("token-123");
    MockWebSocket.instances[0].emitClose();

    vi.advanceTimersByTime(1000);

    expect(MockWebSocket.instances).toHaveLength(2);
  });

  it("sends heartbeat pings when the socket is open", () => {
    const manager = new WebSocketManager();
    manager.connect("token-123");
    MockWebSocket.instances[0].emitOpen();

    vi.advanceTimersByTime(25_000);

    expect(MockWebSocket.instances[0].sent).toContain(
      JSON.stringify({ type: "ping", payload: {} }),
    );
  });

  it("routes text chunks and deal alerts into stores", () => {
    const manager = new WebSocketManager();
    manager.connect("token-123");
    MockWebSocket.instances[0].emitOpen();

    MockWebSocket.instances[0].emitMessage({
      type: "text_chunk",
      session_id: "session-1",
      payload: {
        conversation_id: "session-1",
        text: "Hello",
        is_final: false,
      },
    });
    MockWebSocket.instances[0].emitMessage({
      type: "text_chunk",
      session_id: "session-1",
      payload: {
        conversation_id: "session-1",
        text: " world",
        is_final: true,
      },
    });
    MockWebSocket.instances[0].emitMessage({
      type: "deal_alert",
      payload: {
        event_id: "evt-1",
        listing_id: "listing-1",
        title: "Madrid centre apartment",
        address: "Madrid",
        price_eur: 320000,
        area_m2: 82,
        deal_score: 91,
        deal_tier: 1,
        rule_name: "Madrid under 350k",
        triggered_at: "2026-04-17T00:00:00Z",
      },
    });

    expect(useChatStore.getState().messages[0].content).toBe("Hello world");
    expect(useNotificationStore.getState().alerts).toHaveLength(1);
    expect(useNotificationStore.getState().toastQueue).toHaveLength(1);
  });

  it("disconnects cleanly without scheduling another reconnect", () => {
    const manager = new WebSocketManager();
    manager.connect("token-123");
    MockWebSocket.instances[0].emitOpen();

    manager.disconnect();
    vi.advanceTimersByTime(30_000);

    expect(MockWebSocket.instances).toHaveLength(1);
  });
});
