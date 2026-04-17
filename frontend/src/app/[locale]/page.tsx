"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "next-auth/react";

import { ChatInput } from "@/components/chat/ChatInput";
import { ConversationSidebar } from "@/components/chat/ConversationSidebar";
import { useChatWebSocket } from "@/hooks/useChatWebSocket";
import { useRouter } from "@/i18n/routing";
import { useChatStore } from "@/stores/chatStore";

export default function LocaleHomePage() {
  const router = useRouter();
  const t = useTranslations("chat");
  const tMeta = useTranslations("meta");
  const { data: session } = useSession();

  const [sidebarOpen, setSidebarOpen] = useState(false);

  const activeSessionId = useChatStore((state) => state.activeSessionId);
  const createSession = useChatStore((state) => state.createSession);
  const addMessage = useChatStore((state) => state.addMessage);
  const { send } = useChatWebSocket({
    jwt: session?.accessToken,
    sessionId: activeSessionId,
  });

  const handleSend = async (content: string) => {
    const sessionId = activeSessionId ?? createSession();

    addMessage(sessionId, {
      id: `user-${Date.now()}`,
      role: "user",
      content,
      attachments: [],
      timestamp: Date.now(),
      isStreaming: false,
    });

    send({
      type: "chat_message",
      sessionId,
      content,
    });

    router.push("/chat");
  };

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[minmax(0,1fr)_20rem]">
      <main className="flex min-h-screen items-center justify-center px-6 py-10">
        <section className="w-full max-w-5xl text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.28em] text-teal-700">
            EstateGap
          </p>
          <h1 className="mt-5 text-5xl font-semibold tracking-tight text-slate-950 sm:text-6xl">
            {t("title")}
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-slate-600">
            {tMeta("tagline")}
          </p>

          <div className="mt-12">
            <ChatInput autoFocus hero onSend={handleSend} />
          </div>

          <p className="mt-6 text-sm text-slate-500">{t("voicePrompt")}</p>
        </section>
      </main>

      <ConversationSidebar onOpenChange={setSidebarOpen} open={sidebarOpen} />
    </div>
  );
}
