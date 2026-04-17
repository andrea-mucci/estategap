"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "next-auth/react";

import { ChatWindow } from "@/components/chat/ChatWindow";
import { ConversationSidebar } from "@/components/chat/ConversationSidebar";
import { SearchResults } from "@/components/search/SearchResults";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { useChatStore } from "@/stores/chatStore";

export default function ChatPage() {
  const tCommon = useTranslations("common");
  const { data: session } = useSession();

  const [sidebarOpen, setSidebarOpen] = useState(false);

  const activeSessionId = useChatStore((state) => state.activeSessionId);
  const sessions = useChatStore((state) => state.sessions);
  const createSession = useChatStore((state) => state.createSession);
  const setSessionStatus = useChatStore((state) => state.setSessionStatus);

  useEffect(() => {
    if (!activeSessionId) {
      createSession();
    }
  }, [activeSessionId, createSession]);

  const sessionId = activeSessionId ?? "";
  const activeSession = sessions.get(sessionId);

  if (!activeSessionId || !activeSession) {
    return (
      <div className="grid min-h-screen place-items-center px-6">
        <div className="rounded-[32px] bg-white/80 px-6 py-5 text-sm text-slate-500">
          {tCommon("loading")}…
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[20rem_minmax(0,1fr)]">
      <ConversationSidebar onOpenChange={setSidebarOpen} open={sidebarOpen} />

      <main className="space-y-6 px-4 py-4 sm:px-6 sm:py-6">
        <ErrorBoundary
          fallback={
            <div className="rounded-[32px] border border-red-200 bg-red-50 p-5 text-sm text-red-700">
              The chat window hit an unexpected error.
            </div>
          }
        >
          <ChatWindow
            jwt={session?.accessToken}
            onOpenHistory={() => setSidebarOpen(true)}
            sessionId={sessionId}
          />
        </ErrorBoundary>

        <ErrorBoundary
          fallback={
            <div className="rounded-[32px] border border-red-200 bg-red-50 p-5 text-sm text-red-700">
              Search results could not be rendered.
            </div>
          }
        >
          <SearchResults
            criteria={activeSession.criteria}
            onRefineSearch={() => setSessionStatus(sessionId, "searching")}
            status={activeSession.status}
          />
        </ErrorBoundary>
      </main>
    </div>
  );
}
