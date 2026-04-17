"use client";

import { Menu, RotateCcw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef } from "react";

import { ChatInput } from "@/components/chat/ChatInput";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { TypingIndicator } from "@/components/chat/TypingIndicator";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useChatWebSocket } from "@/hooks/useChatWebSocket";
import { useChatStore } from "@/stores/chatStore";
import type { ChipItem, CriteriaField } from "@/types/chat";

export function ChatWindow({
  jwt,
  onOpenHistory,
  sessionId,
}: {
  jwt?: string | null;
  onOpenHistory: () => void;
  sessionId: string;
}) {
  const t = useTranslations("chat");
  const tCommon = useTranslations("common");

  const scrollRef = useRef<HTMLDivElement | null>(null);

  const session = useChatStore((state) => state.sessions.get(sessionId));
  const addMessage = useChatStore((state) => state.addMessage);
  const confirmSearch = useChatStore((state) => state.confirmSearch);
  const updateCriteria = useChatStore((state) => state.updateCriteria);
  const { reconnect, send, status } = useChatWebSocket({ jwt, sessionId });

  useEffect(() => {
    const container = scrollRef.current;

    if (!container) {
      return;
    }

    container.scrollTop = container.scrollHeight;
  }, [session?.messages, session?.streamingMessageId]);

  const handleSend = async (content: string) => {
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
  };

  const handleChipSelect = (chip: ChipItem) => {
    void handleSend(chip.label);
  };

  const handleImageFeedback = (listingId: string, action: "like" | "dislike") => {
    send({
      type: "image_feedback",
      action,
      listingId,
      sessionId,
    });
  };

  const handleUpdateCriteria = (field: CriteriaField, value: string) => {
    updateCriteria(sessionId, {
      [field.key]: value,
    });
  };

  const handleConfirmCriteria = () => {
    const latest = useChatStore.getState().sessions.get(sessionId);

    if (!latest) {
      return;
    }

    confirmSearch(sessionId);
    send({
      type: "criteria_confirm",
      sessionId,
      criteria: latest.criteria,
    });
  };

  const lastMessage = session?.messages.at(-1);

  return (
    <section className="surface-glass flex min-h-[60vh] flex-col rounded-[36px] border border-white/70 shadow-[0_35px_120px_-70px_rgba(15,23,42,0.9)]">
      <header className="flex items-center justify-between gap-3 border-b border-white/70 px-5 py-4">
        <div className="flex items-center gap-3">
          <Button
            aria-label={tCommon("menu")}
            className="md:hidden"
            onClick={onOpenHistory}
            size="icon"
            variant="outline"
          >
            <Menu className="h-5 w-5" />
          </Button>

          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-teal-700">
              EstateGap
            </p>
            <h1 className="mt-1 text-2xl font-semibold text-slate-950">{t("title")}</h1>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge>{status}</Badge>
          {(status === "disconnected" || status === "error") && jwt ? (
            <Button
              aria-label={t("reconnect")}
              onClick={() => reconnect()}
              size="icon"
              variant="outline"
            >
              <RotateCcw className="h-4 w-4" />
            </Button>
          ) : null}
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-hidden">
        <div className="h-full space-y-4 overflow-y-auto px-5 py-5" ref={scrollRef}>
          {!session || session.messages.length === 0 ? (
            <div className="rounded-[28px] bg-slate-50 p-6 text-sm text-slate-500">
              {t("newConversation")}
            </div>
          ) : (
            session.messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                onConfirmCriteria={handleConfirmCriteria}
                onImageFeedback={handleImageFeedback}
                onSelectChip={handleChipSelect}
                onUpdateCriteria={handleUpdateCriteria}
              />
            ))
          )}

          {session?.streamingMessageId &&
          lastMessage?.id === session.streamingMessageId &&
          !lastMessage.content.trim() ? (
            <div className="flex justify-start">
              <TypingIndicator />
            </div>
          ) : null}
        </div>
      </div>

      <div className="border-t border-white/70 px-4 py-4">
        <ChatInput isStreaming={Boolean(session?.streamingMessageId)} onSend={handleSend} />
      </div>
    </section>
  );
}
