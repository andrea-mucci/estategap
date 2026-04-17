"use client";

import type { InfiniteData } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import type { ListingSummary, PaginatedList } from "@/lib/api";
import { flattenInfiniteItems } from "@/lib/listing-search";

import { InfiniteScrollSentinel } from "./InfiniteScrollSentinel";
import { SearchListingRow } from "./SearchListingRow";

export function SearchResultsList({
  hasNextPage,
  isFetchingNextPage,
  isLoading,
  onLoadMore,
  pages,
}: {
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  isLoading: boolean;
  onLoadMore: () => void;
  pages?: InfiniteData<PaginatedList<ListingSummary>>;
}) {
  const t = useTranslations("searchPage");
  const listings = flattenInfiniteItems(pages?.pages);
  const totalCount = pages?.pages[0]?.total ?? 0;

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 6 }).map((_, index) => (
          <SearchListingRow key={index} loading />
        ))}
      </div>
    );
  }

  if (totalCount === 0) {
    return (
      <div className="rounded-[28px] border border-dashed border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
        {t("empty")}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {listings.map((listing) => (
        <SearchListingRow key={listing.id} listing={listing} />
      ))}
      {hasNextPage ? (
        <InfiniteScrollSentinel
          isLoading={isFetchingNextPage}
          onVisible={onLoadMore}
        />
      ) : (
        <p className="py-4 text-center text-sm text-slate-400">{t("noMore")}</p>
      )}
    </div>
  );
}
