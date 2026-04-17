"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ChipSelector } from "@/components/chat/ChipSelector";
import { CriteriaSummaryCard } from "@/components/chat/CriteriaSummaryCard";
import { ImageCarousel } from "@/components/chat/ImageCarousel";
import { cn } from "@/lib/utils";
import type { ChatMessage, ChipItem, CriteriaField } from "@/types/chat";

type MessageBubbleProps = {
  message: ChatMessage;
  onConfirmCriteria: () => void;
  onImageFeedback: (listingId: string, action: "like" | "dislike") => void;
  onSelectChip: (chip: ChipItem) => void;
  onUpdateCriteria: (field: CriteriaField, value: string) => void;
};

function AttachmentRenderer({
  message,
  onConfirmCriteria,
  onImageFeedback,
  onSelectChip,
  onUpdateCriteria,
}: MessageBubbleProps) {
  return message.attachments.map((attachment, index) => {
    switch (attachment.type) {
      case "chips":
        return (
          <ChipSelector
            chips={attachment.chips}
            key={`${message.id}-chips-${index}`}
            onSelect={onSelectChip}
          />
        );
      case "carousel":
        return (
          <ImageCarousel
            images={attachment.images}
            key={`${message.id}-carousel-${index}`}
            onFeedback={onImageFeedback}
          />
        );
      case "criteria":
        return (
          <CriteriaSummaryCard
            fields={attachment.fields}
            key={`${message.id}-criteria-${index}`}
            onConfirm={onConfirmCriteria}
            onUpdateField={onUpdateCriteria}
          />
        );
      case "listings":
        return null;
    }
  });
}

export function MessageBubble(props: MessageBubbleProps) {
  const { message } = props;
  const isUser = message.role === "user";

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <article
        className={cn(
          "max-w-[92%] space-y-4 rounded-[30px] border p-4 shadow-[0_24px_70px_-50px_rgba(15,23,42,0.8)]",
          isUser
            ? "border-teal-800 bg-teal-700 text-white"
            : "border-white/70 bg-white/95 text-slate-950",
        )}
      >
        {message.content ? (
          isUser ? (
            <p className="whitespace-pre-wrap text-sm leading-7">{message.content}</p>
          ) : (
            <ReactMarkdown
              className="chat-markdown prose prose-sm max-w-none"
              remarkPlugins={[remarkGfm]}
            >
              {message.content}
            </ReactMarkdown>
          )
        ) : null}

        <AttachmentRenderer {...props} />
      </article>
    </div>
  );
}
