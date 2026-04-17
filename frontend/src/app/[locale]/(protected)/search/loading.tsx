import { Skeleton } from "@/components/ui/skeleton";

export default function SearchLoading() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-10 w-56" />
      <div className="lg:grid lg:grid-cols-[280px_1fr] lg:gap-6">
        <div className="hidden space-y-4 rounded-[32px] border border-white/70 bg-white/90 p-5 lg:block">
          {Array.from({ length: 8 }).map((_, index) => (
            <Skeleton className="h-10 w-full" key={index} />
          ))}
        </div>
        <div className="space-y-4">
          <Skeleton className="h-20 w-full rounded-[28px]" />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton className="h-[320px] w-full rounded-[28px]" key={index} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

