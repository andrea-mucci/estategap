import { beforeEach, describe, expect, it } from "vitest";

import { useChatStore } from "./chatStore";

describe("chatStore", () => {
  beforeEach(() => {
    useChatStore.setState({
      sessionId: null,
      messages: [],
      criteria: null,
      wsStatus: "disconnected",
    });
  });

  it("adds a message", () => {
    useChatStore.getState().addMessage({
      id: "msg-1",
      role: "user",
      type: "text",
      content: "Hello",
      timestamp: 1,
    });

    expect(useChatStore.getState().messages).toHaveLength(1);
    expect(useChatStore.getState().messages[0].content).toBe("Hello");
  });

  it("accumulates streaming chunks", () => {
    useChatStore.getState().appendChunk("conv-1", "Hello", false);
    useChatStore.getState().appendChunk("conv-1", " world", true);

    expect(useChatStore.getState().messages).toHaveLength(1);
    expect(useChatStore.getState().messages[0].content).toBe("Hello world");
    expect(useChatStore.getState().messages[0].isStreaming).toBe(false);
  });

  it("stores criteria summaries", () => {
    useChatStore.getState().setCriteria({
      conversationId: "conv-2",
      criteria: {
        city: "Madrid",
      },
      readyToSearch: true,
    });

    expect(useChatStore.getState().criteria?.conversationId).toBe("conv-2");
    expect(useChatStore.getState().criteria?.readyToSearch).toBe(true);
  });
});
