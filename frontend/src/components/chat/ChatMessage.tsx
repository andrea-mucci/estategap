"use client";

import { useTranslations } from "next-intl";

import { ListingCarousel } from "@/components/listings/ListingCarousel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useWebSocket } from "@/providers/WSProvider";
import type { ChatMessage as ChatMessageModel } from "@/stores/chatStore";
import { useChatStore } from "@/stores/chatStore";

export function ChatMessage({ message }: { message: ChatMessageModel }) {
  const t = useTranslations("chat");
  const manager = useWebSocket();
  const sessionId = useChatStore((state) => state.sessionId);
  const addMessage = useChatStore((state) => state.addMessage);

  const bubbleClassName =
    message.role === "user"
      ? "ml-auto bg-slate-950 text-white"
      : "mr-auto bg-white text-slate-900";

  return (
    <div
      className={cn(
        "max-w-[90%] rounded-[28px] border border-white/70 p-4 shadow-lg",
        bubbleClassName,
      )}
    >
      {message.type === "text" || message.type === "error" ? (
        <p className="whitespace-pre-wrap text-sm leading-6">
          {message.content}
          {message.isStreaming ? <span className="ml-1 animate-pulse">▍</span> : null}
        </p>
      ) : null}

      {message.type === "chips" && message.chips ? (
        <div className="space-y-3">
          <p className="text-sm font-medium text-slate-600">{t("chooseOption")}</p>
          <div className="flex flex-wrap gap-2">
            {message.chips.map((chip) => (
              <Button
                key={chip.value}
                onClick={() => {
                  if (!sessionId) {
                    return;
                  }

                  addMessage({
                    id: `chip-${chip.value}`,
                    role: "user",
                    type: "text",
                    content: chip.label,
                    timestamp: Date.now(),
                  });

                  manager.send({
                    type: "chat_message",
                    session_id: sessionId,
                    payload: {
                      user_message: chip.label,
                      country_code: "ES",
                    },
                  });
                }}
                variant="outline"
              >
                {chip.label}
              </Button>
            ))}
          </div>
        </div>
      ) : null}

      {message.type === "carousel" && message.carousel ? (
        <ListingCarousel
          items={message.carousel.map((listing) => ({
            id: listing.listing_id,
            title: listing.title,
            city: listing.city,
            imageUrl: listing.photo_urls[0],
            price: listing.price_eur,
            area: listing.area_m2,
            dealScore: listing.deal_score,
            href: `/listing/${listing.listing_id}`,
          }))}
        />
      ) : null}

      {message.type === "criteria" && message.criteria ? (
        <div className="space-y-3 text-sm text-slate-700">
          <p className="font-semibold text-slate-900">Criteria ready</p>
          <pre className="overflow-auto rounded-3xl bg-slate-50 p-4 text-xs">
            {JSON.stringify(message.criteria.criteria, null, 2)}
          </pre>
          <Badge>{message.criteria.readyToSearch ? "Ready to search" : "Needs edits"}</Badge>
        </div>
      ) : null}

      {message.type === "results" && message.results ? (
        <div className="space-y-3">
          <p className="text-sm font-semibold text-slate-900">
            {message.results.total_count} results
          </p>
          <div className="space-y-2">
            {message.results.listings.map((listing) => (
              <div
                className="rounded-3xl bg-slate-50 p-3 text-sm text-slate-700"
                key={listing.listing_id}
              >
                <p className="font-semibold text-slate-900">
                  {listing.title || listing.listing_id}
                </p>
                <p>{listing.city}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
