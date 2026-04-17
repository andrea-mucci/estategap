"use client";

import * as React from "react";

export function TooltipProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export function Tooltip({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export function TooltipTrigger({
  children,
  asChild,
}: {
  children: React.ReactNode;
  asChild?: boolean;
}) {
  if (asChild && React.isValidElement(children)) {
    return children;
  }

  return <span>{children}</span>;
}

export function TooltipContent({
  children,
}: {
  children: React.ReactNode;
}) {
  return <span className="sr-only">{children}</span>;
}
