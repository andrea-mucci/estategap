import { cn } from "@/lib/utils";

import { Skeleton } from "./skeleton";

export function LoadingSkeleton({
  rows = 4,
  className,
}: {
  rows?: number;
  className?: string;
}) {
  return (
    <div className={cn("space-y-3", className)}>
      {Array.from({ length: rows }).map((_, index) => (
        <Skeleton
          className={cn(
            "h-5",
            index === 0 ? "w-11/12" : index === rows - 1 ? "w-5/12" : "w-full",
          )}
          key={index}
        />
      ))}
    </div>
  );
}
