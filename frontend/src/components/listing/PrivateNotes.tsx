"use client";

import { AlertCircle, Check, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { useCrmStatus } from "@/hooks/useCrmStatus";
import { usePrivateNotes } from "@/hooks/usePrivateNotes";

export function PrivateNotes({
  listingId,
}: {
  listingId: string;
}) {
  const t = useTranslations("listingDetail");
  const { crmEntry } = useCrmStatus(listingId);
  const { notes, saveStatus, setNotes } = usePrivateNotes(listingId, crmEntry?.notes ?? "");

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-950">{t("privateNotes")}</h2>
          <p className="text-sm text-slate-500">{t("privateNotesSubtitle")}</p>
        </div>
        {saveStatus === "saving" ? (
          <Badge>
            <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
            {t("saving")}
          </Badge>
        ) : null}
        {saveStatus === "saved" ? (
          <Badge>
            <Check className="mr-2 h-3.5 w-3.5" />
            {t("saved")}
          </Badge>
        ) : null}
        {saveStatus === "error" ? (
          <Badge className="bg-rose-50 text-rose-700">
            <AlertCircle className="mr-2 h-3.5 w-3.5" />
            {t("saveFailed")}
          </Badge>
        ) : null}
      </div>
      <Textarea
        className="resize-none"
        onChange={(event) => setNotes(event.target.value)}
        placeholder={t("privateNotesPlaceholder")}
        value={notes}
      />
    </section>
  );
}
