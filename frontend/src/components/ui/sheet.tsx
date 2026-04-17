"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

type SheetContextValue = {
  open: boolean;
  setOpen: (value: boolean) => void;
};

const SheetContext = React.createContext<SheetContextValue | null>(null);

function useSheetContext() {
  const context = React.useContext(SheetContext);

  if (!context) {
    throw new Error("Sheet components must be used within Sheet");
  }

  return context;
}

export function Sheet({
  children,
  open,
  onOpenChange,
}: {
  children: React.ReactNode;
  open?: boolean;
  onOpenChange?: (value: boolean) => void;
}) {
  const [internalOpen, setInternalOpen] = React.useState(false);
  const isControlled = open !== undefined;
  const value = isControlled ? open : internalOpen;
  const setValue = onOpenChange ?? setInternalOpen;

  return (
    <SheetContext.Provider value={{ open: value, setOpen: setValue }}>
      {children}
    </SheetContext.Provider>
  );
}

export function SheetTrigger({
  asChild,
  children,
}: {
  asChild?: boolean;
  children: React.ReactNode;
}) {
  const { open, setOpen } = useSheetContext();

  if (asChild && React.isValidElement(children)) {
    const child = children as React.ReactElement<{
      onClick?: React.MouseEventHandler;
    }>;

    return React.cloneElement(child, {
      onClick: (event) => {
        child.props.onClick?.(event);
        setOpen(!open);
      },
    });
  }

  return (
    <button type="button" onClick={() => setOpen(!open)}>
      {children}
    </button>
  );
}

export function SheetContent({
  side = "left",
  className,
  children,
}: {
  side?: "left" | "right" | "bottom";
  className?: string;
  children: React.ReactNode;
}) {
  const { open, setOpen } = useSheetContext();

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <button
        aria-label="Close menu"
        className="absolute inset-0 bg-slate-950/45 backdrop-blur-sm"
        onClick={() => setOpen(false)}
        type="button"
      />
      <div
        className={cn(
          side === "bottom"
            ? "absolute bottom-0 left-0 right-0 rounded-t-[32px] bg-white p-6 shadow-2xl"
            : "absolute top-0 h-full w-[85vw] max-w-sm bg-white p-6 shadow-2xl",
          side === "left" ? "left-0" : "",
          side === "right" ? "right-0" : "",
          className,
        )}
      >
        {children}
      </div>
    </div>
  );
}

export function SheetClose({
  children,
  asChild,
}: {
  children: React.ReactNode;
  asChild?: boolean;
}) {
  const { setOpen } = useSheetContext();

  if (asChild && React.isValidElement(children)) {
    const child = children as React.ReactElement<{
      onClick?: React.MouseEventHandler;
    }>;

    return React.cloneElement(child, {
      onClick: (event) => {
        child.props.onClick?.(event);
        setOpen(false);
      },
    });
  }

  return (
    <button type="button" onClick={() => setOpen(false)}>
      {children}
    </button>
  );
}
