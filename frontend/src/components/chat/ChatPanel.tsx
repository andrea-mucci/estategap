"use client";

import { useTranslations } from "next-intl";

import { ChatMessage } from "@/components/chat/ChatMessage";
import { Badge } from "@/components/ui/badge";
import { useChatStore } from "@/stores/chatStore";

export function ChatPanel() {
  const t = useTranslations("chat");
  const messages = useChatStore((state) => state.messages);
  const wsStatus = useChatStore((state) => state.wsStatus);

  return (
    <section className="space-y-4 rounded-[36px] border border-white/70 bg-white/90 p-6 shadow-xl">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-teal-700">
            {t("newSession")}
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-slate-950">
            {t("startConversation")}
          </h2>
        </div>
        <Badge>{wsStatus}</Badge>
      </div>

      {messages.length === 0 ? (
        <div className="rounded-[28px] bg-slate-50 p-6 text-sm text-slate-500">
          {t("disconnected")}
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}
        </div>
      )}
    </section>
  );
}
