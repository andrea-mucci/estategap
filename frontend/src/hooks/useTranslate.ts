"use client";

import { useMutation } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useSession } from "next-auth/react";
import { useState } from "react";

import { translateText } from "@/lib/api";
import { LOCALE_TO_DEEPL } from "@/lib/listing-search";
import { useNotificationStore } from "@/stores/notificationStore";

export { LOCALE_TO_DEEPL } from "@/lib/listing-search";

export function useTranslate() {
  const locale = useLocale();
  const t = useTranslations("listingDetail");
  const { data: session } = useSession();
  const pushToast = useNotificationStore((state) => state.pushToast);
  const [translatedText, setTranslatedText] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (text: string) =>
      translateText(session?.accessToken, text, LOCALE_TO_DEEPL[locale] ?? "EN-GB"),
    onError: (error) => {
      pushToast({
        description: t("translationUnavailableDescription"),
        durationMs: 4000,
        title: t("translationUnavailable"),
        type: "error",
      });
    },
    onSuccess: (payload) => {
      setTranslatedText(payload.translated_text);
    },
  });

  return {
    isPending: mutation.isPending,
    reset: () => setTranslatedText(null),
    translate: mutation.mutateAsync,
    translatedText,
  };
}
