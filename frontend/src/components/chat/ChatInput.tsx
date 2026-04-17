"use client";

import { Loader2, Mic, SendHorizontal } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useEffectEvent, useRef, useState } from "react";

import { VoiceInput } from "@/components/chat/VoiceInput";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type ChatInputProps = {
  autoFocus?: boolean;
  className?: string;
  hero?: boolean;
  isStreaming?: boolean;
  onSend: (value: string) => Promise<void> | void;
};

export function ChatInput({
  autoFocus = false,
  className,
  hero = false,
  isStreaming = false,
  onSend,
}: ChatInputProps) {
  const locale = useLocale();
  const t = useTranslations("chat");

  const [value, setValue] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [voiceAvailable, setVoiceAvailable] = useState(true);

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const resizeTextarea = useEffectEvent(() => {
    const textarea = textareaRef.current;

    if (!textarea) {
      return;
    }

    textarea.style.height = "0px";
    textarea.style.height = `${Math.min(textarea.scrollHeight, hero ? 220 : 180)}px`;
  });

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const speechWindow = window as Window & {
      SpeechRecognition?: unknown;
      webkitSpeechRecognition?: unknown;
    };

    const hasSpeechApi = Boolean(
      speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition,
    );
    const hasFallback =
      typeof MediaRecorder !== "undefined" &&
      Boolean(navigator.mediaDevices?.getUserMedia);

    setVoiceAvailable(hasSpeechApi || hasFallback);
  }, []);

  useEffect(() => {
    resizeTextarea();
  }, [resizeTextarea, value]);

  const submit = useEffectEvent(async () => {
    const nextValue = value.trim();

    if (!nextValue || submitting) {
      return;
    }

    setSubmitting(true);
    setValue("");

    try {
      await onSend(nextValue);
    } catch {
      setValue(nextValue);
    } finally {
      setSubmitting(false);
    }
  });

  return (
    <>
      <form
        className={cn(
          "surface-glass flex w-full items-end gap-3 rounded-[32px] border border-white/70 p-4 shadow-[0_30px_90px_-55px_rgba(15,23,42,0.65)]",
          hero ? "mx-auto max-w-4xl p-5" : "bg-white/90",
          className,
        )}
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <div className="min-w-0 flex-1">
          <textarea
            aria-label={t("placeholder")}
            autoFocus={autoFocus}
            className={cn(
              "max-h-56 min-h-[52px] w-full resize-none border-0 bg-transparent px-1 py-2 text-slate-950 outline-none placeholder:text-slate-400",
              hero ? "text-lg leading-8" : "text-base leading-7",
            )}
            onChange={(event) => setValue(event.target.value)}
            onInput={() => resizeTextarea()}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void submit();
              }
            }}
            placeholder={t("placeholder")}
            ref={textareaRef}
            rows={1}
            value={value}
          />
        </div>

        {voiceAvailable ? (
          <Button
            aria-label={t("mic")}
            className="shrink-0"
            onClick={() => setVoiceOpen(true)}
            size="icon"
            type="button"
            variant="outline"
          >
            <Mic className="h-5 w-5" />
          </Button>
        ) : null}

        <Button
          aria-label={t("send")}
          className="shrink-0 gap-2"
          disabled={!value.trim() || submitting}
          type="submit"
        >
          {submitting || isStreaming ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <SendHorizontal className="h-4 w-4" />
          )}
          {t("send")}
        </Button>
      </form>

      <VoiceInput
        locale={locale}
        onDraftTranscript={setValue}
        onOpenChange={setVoiceOpen}
        onTranscript={setValue}
        open={voiceOpen}
      />
    </>
  );
}
