import { enableMapSet } from "immer";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { immer } from "zustand/middleware/immer";

import type {
  ChatConnectionStatus,
  ChatMessage,
  ChatSessionSummary,
  ChatStore,
  MessageAttachment,
  SessionState,
  SessionStatus,
} from "@/types/chat";

type PersistedChatStore = {
  activeSessionId: string | null;
  sessions: Record<string, SessionState>;
};

type ChatStoreState = ChatStore & {
  connectionStatus: ChatConnectionStatus;
  sessionSummaries: ChatSessionSummary[];
  sidebarOpen: boolean;
  ensureSession: (sessionId: string) => void;
  replaceSessionId: (sourceId: string, targetId: string) => void;
  setConnectionStatus: (status: ChatConnectionStatus) => void;
  setSessionStatus: (sessionId: string, status: SessionStatus) => void;
  setSessionSummaries: (summaries: ChatSessionSummary[]) => void;
  setSidebarOpen: (open: boolean) => void;
  reset: () => void;
};

enableMapSet();

const storage = createJSONStorage<PersistedChatStore>(() => {
  if (typeof window === "undefined") {
    return {
      getItem: () => null,
      removeItem: () => undefined,
      setItem: () => undefined,
    };
  }

  return window.sessionStorage;
});

function createMessageId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createEmptySession(): SessionState {
  return {
    messages: [],
    criteria: {},
    status: "searching",
    streamingMessageId: null,
    snippetText: "",
    updatedAt: Date.now(),
  };
}

function toSnippet(message: ChatMessage | undefined) {
  if (!message) {
    return "";
  }

  const trimmed = message.content.trim();
  return trimmed.slice(0, 100);
}

function upsertSession(map: Map<string, SessionState>, sessionId: string) {
  const existing = map.get(sessionId);

  if (existing) {
    return existing;
  }

  const session = createEmptySession();
  map.set(sessionId, session);
  return session;
}

function upsertStreamingMessage(
  session: SessionState,
  messageId: string,
): ChatMessage {
  const existing = session.messages.find((message) => message.id === messageId);

  if (existing) {
    return existing;
  }

  const message: ChatMessage = {
    id: messageId || createMessageId("assistant"),
    role: "assistant",
    content: "",
    attachments: [],
    timestamp: Date.now(),
    isStreaming: true,
  };

  session.messages.push(message);
  return message;
}

function syncSessionMeta(session: SessionState) {
  const lastAssistantMessage = [...session.messages]
    .reverse()
    .find((message) => message.role === "assistant");
  const fallbackMessage = session.messages.at(-1);

  session.snippetText = toSnippet(lastAssistantMessage ?? fallbackMessage);
  session.updatedAt = Date.now();
}

function criteriaFromAttachments(attachments: MessageAttachment[]) {
  const criteriaAttachment = attachments.find((attachment) => attachment.type === "criteria");

  if (!criteriaAttachment || criteriaAttachment.type !== "criteria") {
    return null;
  }

  return criteriaAttachment.fields.reduce<Record<string, string>>((accumulator, field) => {
    accumulator[field.key] = field.value;
    return accumulator;
  }, {});
}

const initialState = {
  activeSessionId: null as string | null,
  sessions: new Map<string, SessionState>(),
  connectionStatus: "disconnected" as ChatConnectionStatus,
  sessionSummaries: [] as ChatSessionSummary[],
  sidebarOpen: false,
};

export const useChatStore = create<ChatStoreState>()(
  persist(
    immer((set) => ({
      ...initialState,
      ensureSession: (sessionId) =>
        set((state) => {
          upsertSession(state.sessions, sessionId);
        }),
      createSession: (sessionId) => {
        const nextSessionId = sessionId ?? createMessageId("session");

        set((state) => {
          upsertSession(state.sessions, nextSessionId);
          state.activeSessionId = nextSessionId;
        });

        return nextSessionId;
      },
      loadSession: (sessionId) =>
        set((state) => {
          if (!state.sessions.has(sessionId)) {
            state.sessions.set(sessionId, createEmptySession());
          }

          state.activeSessionId = sessionId;
        }),
      replaceSessionId: (sourceId, targetId) =>
        set((state) => {
          if (!sourceId || sourceId === targetId) {
            state.activeSessionId = targetId;
            return;
          }

          const source = state.sessions.get(sourceId);

          if (source) {
            state.sessions.set(targetId, source);
            state.sessions.delete(sourceId);
          } else if (!state.sessions.has(targetId)) {
            state.sessions.set(targetId, createEmptySession());
          }

          if (state.activeSessionId === sourceId || !state.activeSessionId) {
            state.activeSessionId = targetId;
          }
        }),
      addMessage: (sessionId, message) =>
        set((state) => {
          const session = upsertSession(state.sessions, sessionId);

          session.messages.push({
            ...message,
            id: message.id || createMessageId(message.role),
            attachments: message.attachments ?? [],
            timestamp: message.timestamp || Date.now(),
            isStreaming: message.isStreaming ?? false,
          });

          if (message.role === "user") {
            session.status = "searching";
          }

          state.activeSessionId = sessionId;
          syncSessionMeta(session);
        }),
      startStreaming: (sessionId, messageId) =>
        set((state) => {
          const session = upsertSession(state.sessions, sessionId);
          const message = upsertStreamingMessage(session, messageId);

          message.isStreaming = true;
          message.timestamp = Date.now();
          session.streamingMessageId = message.id;
          syncSessionMeta(session);
        }),
      appendChunk: (sessionId, messageId, chunk) =>
        set((state) => {
          const session = upsertSession(state.sessions, sessionId);
          const message = upsertStreamingMessage(session, messageId);

          message.content += chunk;
          message.isStreaming = true;
          message.timestamp = Date.now();
          session.streamingMessageId = message.id;
          syncSessionMeta(session);
        }),
      endStreaming: (sessionId, messageId) =>
        set((state) => {
          const session = upsertSession(state.sessions, sessionId);
          const message = upsertStreamingMessage(session, messageId);

          message.isStreaming = false;
          message.timestamp = Date.now();
          session.streamingMessageId = null;
          syncSessionMeta(session);
        }),
      setAttachments: (sessionId, messageId, attachments) =>
        set((state) => {
          const session = upsertSession(state.sessions, sessionId);
          const message = upsertStreamingMessage(session, messageId);

          message.attachments = attachments;
          message.timestamp = Date.now();

          const nextCriteria = criteriaFromAttachments(attachments);
          if (nextCriteria) {
            session.criteria = nextCriteria;
            session.status = "confirming";
          }

          if (attachments.some((attachment) => attachment.type === "listings")) {
            session.status = "complete";
          }

          syncSessionMeta(session);
        }),
      updateCriteria: (sessionId, patch) =>
        set((state) => {
          const session = upsertSession(state.sessions, sessionId);
          session.criteria = {
            ...session.criteria,
            ...patch,
          };
          session.status = "confirming";
          syncSessionMeta(session);
        }),
      confirmSearch: (sessionId) =>
        set((state) => {
          const session = upsertSession(state.sessions, sessionId);
          session.status = "confirmed";
          session.updatedAt = Date.now();
        }),
      setConnectionStatus: (status) =>
        set(() => ({
          connectionStatus: status,
        })),
      setSessionStatus: (sessionId, status) =>
        set((state) => {
          const session = upsertSession(state.sessions, sessionId);
          session.status = status;
          session.updatedAt = Date.now();
        }),
      setSessionSummaries: (summaries) =>
        set(() => ({
          sessionSummaries: summaries,
        })),
      setSidebarOpen: (open) =>
        set(() => ({
          sidebarOpen: open,
        })),
      reset: () =>
        set(() => ({
          ...initialState,
          sessions: new Map<string, SessionState>(),
        })),
    })),
    {
      name: "estategap-chat-store",
      storage,
      partialize: (state) => ({
        activeSessionId: state.activeSessionId,
        sessions: Object.fromEntries(state.sessions.entries()),
      }),
      merge: (persistedState, currentState) => {
        const persisted = persistedState as PersistedChatStore | undefined;

        return {
          ...currentState,
          activeSessionId: persisted?.activeSessionId ?? currentState.activeSessionId,
          sessions: new Map(Object.entries(persisted?.sessions ?? {})),
        };
      },
    },
  ),
);
