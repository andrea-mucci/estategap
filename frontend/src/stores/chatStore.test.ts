import { beforeEach, describe, expect, it } from "vitest";

import { useChatStore } from "./chatStore";

describe("chatStore", () => {
  beforeEach(() => {
    useChatStore.getState().reset();
  });

  it("creates and loads chat sessions", () => {
    const sessionId = useChatStore.getState().createSession("session-1");

    expect(sessionId).toBe("session-1");
    expect(useChatStore.getState().activeSessionId).toBe("session-1");
    expect(useChatStore.getState().sessions.has("session-1")).toBe(true);
  });

  it("appends streaming chunks into a single assistant message", () => {
    const sessionId = useChatStore.getState().createSession("session-1");

    useChatStore.getState().startStreaming(sessionId, "assistant-1");
    useChatStore.getState().appendChunk(sessionId, "assistant-1", "Hello");
    useChatStore.getState().appendChunk(sessionId, "assistant-1", " world");
    useChatStore.getState().endStreaming(sessionId, "assistant-1");

    const session = useChatStore.getState().sessions.get(sessionId);

    expect(session?.messages).toHaveLength(1);
    expect(session?.messages[0].content).toBe("Hello world");
    expect(session?.messages[0].isStreaming).toBe(false);
    expect(session?.streamingMessageId).toBeNull();
  });

  it("hydrates criteria from attachments and marks the session as confirming", () => {
    const sessionId = useChatStore.getState().createSession("session-1");

    useChatStore.getState().setAttachments(sessionId, "assistant-1", [
      {
        type: "criteria",
        fields: [
          {
            key: "city",
            label: "City",
            value: "Barcelona",
            inputType: "text",
          },
        ],
      },
    ]);

    const session = useChatStore.getState().sessions.get(sessionId);

    expect(session?.criteria.city).toBe("Barcelona");
    expect(session?.status).toBe("confirming");
  });
});
