"use client";

import { formatDistanceToNow } from "date-fns";
import { useQuery } from "@tanstack/react-query";
import { History } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSession } from "next-auth/react";
import { useEffect } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Link, useRouter } from "@/i18n/routing";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/stores/chatStore";
import type { ChatSessionSummary } from "@/types/chat";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080").replace(
  /\/$/,
  "",
);

async function fetchSessionSummaries(accessToken: string) {
  const response = await fetch(`${API_BASE_URL}/api/chat/sessions?limit=20`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    throw new Error("Failed to load chat sessions");
  }

  const payload = (await response.json()) as {
    sessions?: ChatSessionSummary[];
  };

  return payload.sessions ?? [];
}

export function ConversationSidebar({
  onOpenChange,
  open,
}: {
  onOpenChange: (open: boolean) => void;
  open: boolean;
}) {
  const router = useRouter();
  const t = useTranslations("chat");

  const { data: session } = useSession();

  const activeSessionId = useChatStore((state) => state.activeSessionId);
  const sessions = useChatStore((state) => state.sessions);
  const createSession = useChatStore((state) => state.createSession);
  const loadSession = useChatStore((state) => state.loadSession);
  const setSessionSummaries = useChatStore((state) => state.setSessionSummaries);
  const remoteSummaries = useChatStore((state) => state.sessionSummaries);

  const sessionsQuery = useQuery({
    enabled: Boolean(session?.accessToken),
    queryFn: () => fetchSessionSummaries(session!.accessToken),
    queryKey: ["chat-sessions"],
    staleTime: 30_000,
  });

  useEffect(() => {
    if (sessionsQuery.data) {
      setSessionSummaries(sessionsQuery.data);
    }
  }, [sessionsQuery.data, setSessionSummaries]);

  const localSummaries = [...sessions.entries()].map(([sessionId, localSession]) => ({
    sessionId,
    snippetText: localSession.snippetText,
    updatedAt: new Date(localSession.updatedAt).toISOString(),
    status: localSession.status,
  }));

  const mergedSummaries = [...remoteSummaries, ...localSummaries].reduce<
    Map<string, ChatSessionSummary>
  >((accumulator, item) => {
    const existing = accumulator.get(item.sessionId);

    if (
      !existing ||
      new Date(item.updatedAt).getTime() >= new Date(existing.updatedAt).getTime()
    ) {
      accumulator.set(item.sessionId, item);
    }

    return accumulator;
  }, new Map());

  const orderedSummaries = [...mergedSummaries.values()].sort(
    (left, right) =>
      new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime(),
  );

  const content = (
    <div className="flex h-full flex-col gap-4">
      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-teal-700">
          EstateGap
        </p>
        <h2 className="text-xl font-semibold text-slate-950">{t("historyTitle")}</h2>
      </div>

      <Button
        aria-label={t("newConversation")}
        className="justify-start gap-2"
        onClick={() => {
          const nextSessionId = createSession();
          loadSession(nextSessionId);
          onOpenChange(false);
          router.push("/chat");
        }}
        variant="outline"
      >
        <History className="h-4 w-4" />
        {t("newConversation")}
      </Button>

      {!session?.accessToken ? (
        <div className="rounded-[28px] border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
          <p>{t("saveHistoryPrompt")}</p>
          <Link
            className="mt-3 inline-flex h-11 w-full items-center justify-center rounded-full bg-teal-700 px-4 text-sm font-medium text-white transition hover:bg-teal-800"
            href="/login"
          >
            {t("signInToSave")}
          </Link>
        </div>
      ) : null}

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {orderedSummaries.length === 0 ? (
          <div className="rounded-[28px] bg-slate-50 p-4 text-sm text-slate-500">
            {t("newConversation")}
          </div>
        ) : (
          orderedSummaries.map((summary) => (
            <button
              className={cn(
                "w-full rounded-[24px] border p-4 text-left transition",
                summary.sessionId === activeSessionId
                  ? "border-teal-300 bg-teal-50"
                  : "border-white/70 bg-white/80 hover:bg-white",
              )}
              key={summary.sessionId}
              onClick={() => {
                if (!sessions.has(summary.sessionId)) {
                  createSession(summary.sessionId);
                }

                loadSession(summary.sessionId);
                onOpenChange(false);
                router.push("/chat");
              }}
              type="button"
            >
              <div className="flex items-start justify-between gap-3">
                <p className="line-clamp-2 text-sm font-medium text-slate-950">
                  {summary.snippetText || t("newConversation")}
                </p>
                <Badge>{summary.status}</Badge>
              </div>
              <p className="mt-3 text-xs text-slate-500">
                {formatDistanceToNow(new Date(summary.updatedAt), {
                  addSuffix: true,
                })}
              </p>
            </button>
          ))
        )}
      </div>
    </div>
  );

  return (
    <>
      <aside className="hidden h-full min-h-screen border-r border-white/70 bg-white/60 p-5 backdrop-blur lg:block">
        {content}
      </aside>

      <div className="lg:hidden">
        <Sheet onOpenChange={onOpenChange} open={open}>
          <SheetContent className="p-5" side="left">
            {content}
          </SheetContent>
        </Sheet>
      </div>
    </>
  );
}
