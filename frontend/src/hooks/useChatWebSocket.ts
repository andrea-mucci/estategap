"use client";

import {
  useEffect,
  useEffectEvent,
  useSyncExternalStore,
} from "react";

import { useChatStore } from "@/stores/chatStore";
import type {
  ChatConnectionStatus,
  IncomingWSMessage,
  OutgoingWSMessage,
} from "@/types/chat";

type Subscriber = () => void;

const WS_BASE_URL = (process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:9090").replace(
  /\/$/,
  "",
);

function scheduleFrame(callback: () => void) {
  if (typeof window === "undefined" || typeof window.requestAnimationFrame !== "function") {
    callback();
    return;
  }

  window.requestAnimationFrame(() => callback());
}

function buildWsUrl(jwt: string) {
  return `${WS_BASE_URL}/ws/chat?token=${encodeURIComponent(jwt)}`;
}

class ChatSocketManager {
  private socket: WebSocket | null = null;
  private token: string | null = null;
  private consumers = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private flushTimer: ReturnType<typeof setInterval> | null = null;
  private backoffMs = 1000;
  private shouldReconnect = false;
  private status: ChatConnectionStatus = "disconnected";
  private subscribers = new Set<Subscriber>();
  private chunkBuffer = new Map<string, { chunk: string; messageId: string; sessionId: string }>();
  private queuedMessages: OutgoingWSMessage[] = [];

  subscribe = (subscriber: Subscriber) => {
    this.subscribers.add(subscriber);

    return () => {
      this.subscribers.delete(subscriber);
    };
  };

  getSnapshot = () => this.status;

  attach(sessionId: string | null, jwt?: string | null) {
    this.consumers += 1;

    if (sessionId) {
      useChatStore.getState().ensureSession(sessionId);
      useChatStore.getState().loadSession(sessionId);
    }

    if (jwt) {
      this.connect(jwt);
      return;
    }

    this.updateStatus("disconnected");
  }

  detach() {
    this.consumers = Math.max(0, this.consumers - 1);

    if (this.consumers === 0) {
      this.disconnect(false);
    }
  }

  reconnect() {
    if (!this.token) {
      return;
    }

    this.disconnect(true);
    this.connect(this.token);
  }

  send(message: OutgoingWSMessage) {
    const session = useChatStore.getState().sessions.get(message.sessionId);
    const shouldWaitForStream =
      message.type === "chat_message" && Boolean(session?.streamingMessageId);

    if (
      shouldWaitForStream ||
      !this.socket ||
      this.socket.readyState !== WebSocket.OPEN
    ) {
      this.queuedMessages.push(message);

      if (!shouldWaitForStream && this.token) {
        this.connect(this.token);
      }

      return;
    }

    this.socket.send(JSON.stringify(message));
  }

  private connect(jwt: string) {
    if (
      this.socket &&
      this.token === jwt &&
      (this.socket.readyState === WebSocket.OPEN ||
        this.socket.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    this.token = jwt;
    this.shouldReconnect = true;
    this.clearReconnect();
    this.socket?.close();
    this.updateStatus(this.status === "disconnected" ? "connecting" : "reconnecting");

    const socket = new WebSocket(buildWsUrl(jwt));
    this.socket = socket;

    socket.onopen = () => {
      this.backoffMs = 1000;
      this.updateStatus("connected");
      this.startFlushTimer();
      this.flushQueuedMessages();
    };

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as IncomingWSMessage;
        this.handleMessage(message);
      } catch {
        const sessionId =
          useChatStore.getState().activeSessionId ??
          useChatStore.getState().createSession();

        useChatStore.getState().addMessage(sessionId, {
          id: `assistant-error-${Date.now()}`,
          role: "assistant",
          content: "We could not parse the latest real-time update.",
          attachments: [],
          timestamp: Date.now(),
          isStreaming: false,
        });
      }
    };

    socket.onerror = () => {
      this.updateStatus("error");
    };

    socket.onclose = () => {
      this.stopFlushTimer();

      if (this.shouldReconnect && this.token && this.consumers > 0) {
        this.scheduleReconnect();
        return;
      }

      this.updateStatus("disconnected");
    };
  }

  private disconnect(keepReconnectIntent: boolean) {
    this.shouldReconnect = keepReconnectIntent;
    this.clearReconnect();
    this.stopFlushTimer();

    if (this.socket) {
      const socket = this.socket;
      this.socket = null;
      socket.close();
    }

    if (!keepReconnectIntent) {
      this.updateStatus("disconnected");
    }
  }

  private updateStatus(status: ChatConnectionStatus) {
    this.status = status;
    useChatStore.getState().setConnectionStatus(status);
    this.subscribers.forEach((subscriber) => subscriber());
  }

  private scheduleReconnect() {
    if (this.reconnectTimer || !this.token) {
      return;
    }

    this.updateStatus("reconnecting");
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;

      const token = this.token;
      if (!token) {
        return;
      }

      this.backoffMs = Math.min(this.backoffMs * 2, 30_000);
      this.connect(token);
    }, this.backoffMs);
  }

  private clearReconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private startFlushTimer() {
    if (this.flushTimer) {
      return;
    }

    this.flushTimer = setInterval(() => {
      if (this.chunkBuffer.size === 0) {
        return;
      }

      const nextEntries = [...this.chunkBuffer.values()];
      this.chunkBuffer.clear();

      for (const entry of nextEntries) {
        scheduleFrame(() => {
          useChatStore
            .getState()
            .appendChunk(entry.sessionId, entry.messageId, entry.chunk);
        });
      }
    }, 50);
  }

  private stopFlushTimer() {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
      this.flushTimer = null;
    }
  }

  private flushQueuedMessages() {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return;
    }

    const backlog = [...this.queuedMessages];
    this.queuedMessages = [];

    for (const message of backlog) {
      const session = useChatStore.getState().sessions.get(message.sessionId);

      if (message.type === "chat_message" && session?.streamingMessageId) {
        this.queuedMessages.push(message);
        continue;
      }

      this.socket.send(JSON.stringify(message));
    }
  }

  private flushBufferedMessage(sessionId: string, messageId: string) {
    const key = `${sessionId}:${messageId}`;
    const buffered = this.chunkBuffer.get(key);

    if (!buffered) {
      return;
    }

    this.chunkBuffer.delete(key);
    scheduleFrame(() => {
      useChatStore.getState().appendChunk(sessionId, messageId, buffered.chunk);
    });
  }

  private handleMessage(message: IncomingWSMessage) {
    switch (message.type) {
      case "session_ready": {
        const activeSessionId = useChatStore.getState().activeSessionId;
        if (activeSessionId && activeSessionId !== message.sessionId) {
          useChatStore.getState().replaceSessionId(activeSessionId, message.sessionId);
        } else {
          useChatStore.getState().loadSession(message.sessionId);
        }
        break;
      }
      case "text_chunk": {
        const key = `${message.sessionId}:${message.messageId}`;
        const existing = this.chunkBuffer.get(key);

        useChatStore.getState().startStreaming(message.sessionId, message.messageId);

        this.chunkBuffer.set(key, {
          chunk: `${existing?.chunk ?? ""}${message.chunk}`,
          sessionId: message.sessionId,
          messageId: message.messageId,
        });
        break;
      }
      case "stream_end": {
        this.flushBufferedMessage(message.sessionId, message.messageId);
        scheduleFrame(() => {
          useChatStore.getState().endStreaming(message.sessionId, message.messageId);
        });
        this.flushQueuedMessages();
        break;
      }
      case "attachments": {
        scheduleFrame(() => {
          useChatStore
            .getState()
            .setAttachments(message.sessionId, message.messageId, message.attachments);
        });
        break;
      }
      case "criteria_update": {
        scheduleFrame(() => {
          useChatStore.getState().updateCriteria(message.sessionId, message.criteria);
        });
        break;
      }
      case "error": {
        const sessionId =
          useChatStore.getState().activeSessionId ??
          useChatStore.getState().createSession();

        useChatStore.getState().addMessage(sessionId, {
          id: `assistant-error-${Date.now()}`,
          role: "assistant",
          content: message.message,
          attachments: [],
          timestamp: Date.now(),
          isStreaming: false,
        });

        if (message.code === "AUTH_EXPIRED") {
          this.updateStatus("error");
        }
        break;
      }
    }
  }
}

const manager = new ChatSocketManager();

export function useChatWebSocket({
  jwt,
  sessionId,
}: {
  jwt?: string | null;
  sessionId: string | null;
}) {
  const status = useSyncExternalStore(
    manager.subscribe,
    manager.getSnapshot,
    manager.getSnapshot,
  );

  useEffect(() => {
    manager.attach(sessionId, jwt);

    return () => {
      manager.detach();
    };
  }, [jwt, sessionId]);

  const send = useEffectEvent((message: OutgoingWSMessage) => {
    manager.send(message);
  });

  const reconnect = useEffectEvent(() => {
    manager.reconnect();
  });

  return {
    status,
    send,
    reconnect,
  };
}
