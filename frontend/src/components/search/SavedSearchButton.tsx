"use client";

import { Bookmark } from "lucide-react";
import { useState } from "react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useListingSearchParams } from "@/hooks/useSearchParams";
import { useSavedSearches } from "@/hooks/useSavedSearches";

export function SavedSearchButton() {
  const t = useTranslations("searchPage");
  const tCommon = useTranslations("common");
  const { params } = useListingSearchParams();
  const { createSavedSearch, isSaving } = useSavedSearches();
  const [name, setName] = useState("");
  const [open, setOpen] = useState(false);

  return (
    <Dialog onOpenChange={setOpen} open={open}>
      <DialogTrigger asChild>
        <Button data-testid="save-search-button" variant="outline">
          <Bookmark className="mr-2 h-4 w-4" />
          {t("saveSearch")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <div className="space-y-4">
          <div>
            <h3 className="text-xl font-semibold text-slate-950">{t("saveSearchTitle")}</h3>
            <p className="mt-1 text-sm text-slate-500">
              {t("saveSearchSubtitle")}
            </p>
          </div>
          <Input
            data-testid="save-search-name"
            onChange={(event) => setName(event.target.value)}
            placeholder={t("saveSearchPlaceholder")}
            value={name}
          />
          <div className="flex justify-end gap-2">
            <Button onClick={() => setOpen(false)} variant="ghost">
              {tCommon("cancel")}
            </Button>
            <Button
              data-testid="save-search-confirm"
              disabled={!name.trim() || isSaving}
              onClick={async () => {
                await createSavedSearch({
                  filters: params,
                  name: name.trim(),
                });
                setName("");
                setOpen(false);
              }}
            >
              {tCommon("save")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
