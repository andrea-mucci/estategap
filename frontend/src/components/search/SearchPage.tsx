"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";

import { ErrorDisplay } from "@/components/ui/ErrorDisplay";
import { useInfiniteListings } from "@/hooks/useInfiniteListings";
import { useListingSearchParams } from "@/hooks/useSearchParams";
import { useSearchStore } from "@/stores/searchStore";

import { FilterSidebar } from "./FilterSidebar";
import { FilterSidebarDrawer } from "./FilterSidebarDrawer";
import { SavedSearchButton } from "./SavedSearchButton";
import { SavedSearchDropdown } from "./SavedSearchDropdown";
import { SearchResultsGrid } from "./SearchResultsGrid";
import { SearchResultsList } from "./SearchResultsList";
import { SortDropdown } from "./SortDropdown";
import { ViewToggle } from "./ViewToggle";

export function SearchPage() {
  const t = useTranslations("searchPage");
  const { params } = useListingSearchParams();
  const viewMode = useSearchStore((state) => state.viewMode);
  const query = useInfiniteListings(params);

  const portals = useMemo(() => {
    const values = new Set<string>();
    query.data?.pages.forEach((page) => {
      page.items.forEach((listing) => {
        if (listing.source) {
          values.add(listing.source);
        }
      });
    });
    return [...values];
  }, [query.data?.pages]);

  const resultsContent =
    viewMode === "grid" ? (
      <SearchResultsGrid
        hasNextPage={Boolean(query.hasNextPage)}
        isFetchingNextPage={query.isFetchingNextPage}
        isLoading={query.isPending}
        onLoadMore={() => {
          if (query.hasNextPage) {
            void query.fetchNextPage();
          }
        }}
        pages={query.data}
      />
    ) : (
      <SearchResultsList
        hasNextPage={Boolean(query.hasNextPage)}
        isFetchingNextPage={query.isFetchingNextPage}
        isLoading={query.isPending}
        onLoadMore={() => {
          if (query.hasNextPage) {
            void query.fetchNextPage();
          }
        }}
        pages={query.data}
      />
    );

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold text-slate-950">{t("title")}</h1>
        <p className="max-w-3xl text-sm text-slate-500">
          {t("subtitle")}
        </p>
      </div>

      <div className="lg:grid lg:grid-cols-[280px_1fr] lg:gap-6">
        <div className="hidden lg:block">
          <FilterSidebar portals={portals} />
        </div>

        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-[28px] border border-white/70 bg-white/90 p-4 shadow-[0_20px_50px_-35px_rgba(15,23,42,0.45)]">
            <div>
              <p className="text-sm text-slate-500">{t("showing")}</p>
              <p className="text-xl font-semibold text-slate-950">
                {t("resultsCount", {
                  count: query.totalCount,
                })}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <FilterSidebarDrawer portals={portals} />
              <SavedSearchButton />
              <SavedSearchDropdown />
              <SortDropdown />
              <ViewToggle />
            </div>
          </div>

          {query.isError ? (
            <ErrorDisplay
              error={query.error as Error}
              refetch={() => {
                void query.refetch();
              }}
            />
          ) : (
            resultsContent
          )}
        </div>
      </div>
    </section>
  );
}
