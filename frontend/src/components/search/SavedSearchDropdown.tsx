"use client";

import { BookmarkCheck, Trash2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useListingSearchParams } from "@/hooks/useSearchParams";
import { useSavedSearches } from "@/hooks/useSavedSearches";

export function SavedSearchDropdown() {
  const locale = useLocale();
  const t = useTranslations("searchPage");
  const { setParams } = useListingSearchParams();
  const { deleteSavedSearch, savedSearches } = useSavedSearches();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline">
          <BookmarkCheck className="mr-2 h-4 w-4" />
          {t("saved")}
          {savedSearches.length > 0 ? (
            <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs">
              {savedSearches.length}
            </span>
          ) : null}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[320px] space-y-2">
        {savedSearches.length === 0 ? (
          <p className="px-3 py-2 text-sm text-slate-500">{t("noSavedSearches")}</p>
        ) : (
          savedSearches.map((savedSearch) => (
            <div
              className="flex items-center justify-between gap-2 rounded-2xl px-3 py-2 hover:bg-slate-50"
              key={savedSearch.id}
            >
              <button
                className="min-w-0 flex-1 text-left"
                onClick={() => void setParams(savedSearch.filters)}
                type="button"
              >
                <p className="truncate text-sm font-medium text-slate-900">
                  {savedSearch.name}
                </p>
                <p className="text-xs text-slate-500">
                  {new Date(savedSearch.updated_at).toLocaleDateString(locale)}
                </p>
              </button>
              <Button
                onClick={() => void deleteSavedSearch(savedSearch.id)}
                size="icon"
                variant="ghost"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
