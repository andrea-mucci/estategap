import { Skeleton } from "@/components/ui/skeleton";

export default function ListingLoading() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-[380px] w-full rounded-[32px]" />
      <Skeleton className="h-16 w-full rounded-[28px]" />
      <div className="grid gap-6 xl:grid-cols-2">
        <Skeleton className="h-[320px] w-full rounded-[28px]" />
        <Skeleton className="h-[320px] w-full rounded-[28px]" />
      </div>
      <Skeleton className="h-[320px] w-full rounded-[28px]" />
      <div className="grid gap-6 xl:grid-cols-2">
        <Skeleton className="h-[280px] w-full rounded-[28px]" />
        <Skeleton className="h-[280px] w-full rounded-[28px]" />
      </div>
    </div>
  );
}

