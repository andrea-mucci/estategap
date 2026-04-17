"use client";

import { SendHorizontal } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useWebSocket } from "@/providers/WSProvider";
import { useChatStore } from "@/stores/chatStore";

export function ChatInput() {
  const t = useTranslations("chat");
  const manager = useWebSocket();
  const sessionId = useChatStore((state) => state.sessionId);
  const setSessionId = useChatStore((state) => state.setSessionId);
  const addMessage = useChatStore((state) => state.addMessage);
  const wsStatus = useChatStore((state) => state.wsStatus);
  const [value, setValue] = useState("");

  const disabled = wsStatus !== "connected" || !value.trim();

  return (
    <form
      className="flex flex-col gap-3 rounded-[32px] border border-white/70 bg-white/95 p-4 shadow-xl sm:flex-row"
      onSubmit={(event) => {
        event.preventDefault();

        if (disabled) {
          return;
        }

        const nextSessionId =
          sessionId ?? `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;

        if (!sessionId) {
          setSessionId(nextSessionId);
        }

        addMessage({
          id: `user-${Date.now()}`,
          role: "user",
          type: "text",
          content: value,
          timestamp: Date.now(),
        });

        manager.send({
          type: "chat_message",
          session_id: nextSessionId,
          payload: {
            user_message: value,
            country_code: "ES",
          },
        });

        setValue("");
      }}
    >
      <Input
        onChange={(event) => setValue(event.target.value)}
        placeholder={t("placeholder")}
        value={value}
      />
      <Button className="gap-2" disabled={disabled} type="submit">
        <SendHorizontal className="h-4 w-4" />
        {t("send")}
      </Button>
    </form>
  );
}
