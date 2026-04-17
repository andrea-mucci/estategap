"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useRef } from "react";

export function InfiniteScrollSentinel({
  isLoading,
  onVisible,
}: {
  isLoading: boolean;
  onVisible: () => void;
}) {
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!sentinelRef.current) {
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          onVisible();
        }
      },
      {
        rootMargin: "240px",
      },
    );

    observer.observe(sentinelRef.current);

    return () => {
      observer.disconnect();
    };
  }, [onVisible]);

  return (
    <div className="flex h-20 items-center justify-center" ref={sentinelRef}>
      {isLoading ? <Loader2 className="h-5 w-5 animate-spin text-slate-400" /> : null}
    </div>
  );
}

