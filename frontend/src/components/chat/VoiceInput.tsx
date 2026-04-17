"use client";

import { Loader2, Mic, MicOff } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { useVoiceInput } from "@/hooks/useVoiceInput";

type VoiceInputProps = {
  locale: string;
  onDraftTranscript?: (value: string) => void;
  onOpenChange: (open: boolean) => void;
  onTranscript: (value: string) => void;
  open: boolean;
};

export function VoiceInput({
  locale,
  onDraftTranscript,
  onOpenChange,
  onTranscript,
  open,
}: VoiceInputProps) {
  const t = useTranslations("chat");
  const tCommon = useTranslations("common");

  const {
    errorMessage,
    interimTranscript,
    levels,
    start,
    state,
    stop,
    transcript,
    whisperAvailable,
    isSupported,
  } = useVoiceInput({
    locale,
    onTranscriptChange: onDraftTranscript,
  });

  useEffect(() => {
    if (!open) {
      stop();
      return;
    }

    void start();
  }, [open, start, stop]);

  useEffect(() => {
    if (!transcript) {
      return;
    }

    onTranscript(transcript);
    onOpenChange(false);
  }, [onOpenChange, onTranscript, transcript]);

  const helperText =
    state === "processing"
      ? t("voiceProcessing")
      : state === "listening"
        ? t("voiceListening")
        : errorMessage === "permission"
          ? t("voicePermissionDenied")
          : errorMessage === "unsupported"
            ? t("voiceUnsupported")
            : whisperAvailable && !isSupported
              ? t("voiceFallback")
              : t("voicePrompt");

  return (
    <Dialog onOpenChange={onOpenChange} open={open}>
      <DialogContent className="max-w-xl">
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-teal-700">
                {t("mic")}
              </p>
              <h2 className="mt-2 text-2xl font-semibold text-slate-950">{t("mic")}</h2>
            </div>
            <Button onClick={() => onOpenChange(false)} variant="ghost">
              {tCommon("close")}
            </Button>
          </div>

          <div className="flex items-center gap-4 rounded-[28px] bg-slate-50 px-5 py-4">
            <div
              className={cn(
                "grid h-14 w-14 place-items-center rounded-full border",
                state === "listening"
                  ? "animate-pulse border-teal-400 bg-teal-100 text-teal-700"
                  : "border-slate-200 bg-white text-slate-500",
              )}
            >
              {state === "processing" ? (
                <Loader2 className="h-6 w-6 animate-spin" />
              ) : state === "error" ? (
                <MicOff className="h-6 w-6" />
              ) : (
                <Mic className="h-6 w-6" />
              )}
            </div>

            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-slate-900">{helperText}</p>
              <p className="mt-1 text-sm text-slate-500">
                {interimTranscript || transcript || t("voiceIdle")}
              </p>
            </div>
          </div>

          <div className="flex h-20 items-end gap-2 rounded-[28px] bg-slate-950 px-5 py-4">
            {levels.map((level, index) => (
              <span
                aria-hidden="true"
                className="flex-1 rounded-full bg-teal-300/90 transition-[height] duration-150"
                key={`${index}-${level}`}
                style={{ height: `${level}%` }}
              />
            ))}
          </div>

          {state === "error" ? (
            <div className="rounded-[24px] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {helperText}
            </div>
          ) : null}

          <div className="flex flex-wrap justify-end gap-3">
            <Button onClick={() => onOpenChange(false)} variant="outline">
              {tCommon("cancel")}
            </Button>
            <Button
              onClick={() => {
                if (state === "listening") {
                  stop();
                  return;
                }

                void start();
              }}
              variant={state === "listening" ? "destructive" : "default"}
            >
              {state === "listening" ? tCommon("close") : tCommon("retry")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
