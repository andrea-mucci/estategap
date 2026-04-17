import type { HTMLAttributes, ImgHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Avatar({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "relative flex h-10 w-10 items-center justify-center overflow-hidden rounded-full bg-slate-200 text-sm font-semibold text-slate-700",
        className,
      )}
      {...props}
    />
  );
}

export function AvatarImage({
  className,
  alt,
  ...props
}: ImgHTMLAttributes<HTMLImageElement>) {
  return <img alt={alt} className={cn("h-full w-full object-cover", className)} {...props} />;
}

export function AvatarFallback({
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn("uppercase", className)} {...props} />;
}
