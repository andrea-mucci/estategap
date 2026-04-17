"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

type DropdownContextValue = {
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  contentRef: React.RefObject<HTMLDivElement | null>;
};

const DropdownContext = React.createContext<DropdownContextValue | null>(null);

function useDropdownContext() {
  const context = React.useContext(DropdownContext);

  if (!context) {
    throw new Error("DropdownMenu components must be used within DropdownMenu");
  }

  return context;
}

function composeEventHandlers<E>(
  theirHandler: ((event: E) => void) | undefined,
  ourHandler: (event: E) => void,
) {
  return (event: E) => {
    theirHandler?.(event);
    ourHandler(event);
  };
}

export function DropdownMenu({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  const contentRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (!contentRef.current) {
        return;
      }

      if (contentRef.current.contains(event.target as Node)) {
        return;
      }

      setOpen(false);
    }

    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [open]);

  return (
    <DropdownContext.Provider value={{ open, setOpen, contentRef }}>
      <div className="relative inline-flex">{children}</div>
    </DropdownContext.Provider>
  );
}

export function DropdownMenuTrigger({
  asChild,
  children,
}: {
  asChild?: boolean;
  children: React.ReactNode;
}) {
  const { open, setOpen } = useDropdownContext();

  if (asChild && React.isValidElement(children)) {
    const child = children as React.ReactElement<{
      onClick?: React.MouseEventHandler;
    }>;

    return React.cloneElement(child, {
      onClick: composeEventHandlers(child.props.onClick, () => setOpen(!open)),
    });
  }

  return (
    <button type="button" onClick={() => setOpen(!open)}>
      {children}
    </button>
  );
}

export function DropdownMenuContent({
  align = "start",
  className,
  children,
}: {
  align?: "start" | "end";
  className?: string;
  children: React.ReactNode;
}) {
  const { open, contentRef } = useDropdownContext();

  if (!open) {
    return null;
  }

  return (
    <div
      ref={contentRef}
      className={cn(
        "absolute top-[calc(100%+0.75rem)] z-50 min-w-56 rounded-3xl border border-white/70 bg-white/95 p-2 shadow-2xl backdrop-blur",
        align === "end" ? "right-0" : "left-0",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function DropdownMenuLabel({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400", className)} {...props} />;
}

export function DropdownMenuItem({
  className,
  onSelect,
  children,
}: {
  className?: string;
  onSelect?: () => void;
  children: React.ReactNode;
}) {
  const { setOpen } = useDropdownContext();

  return (
    <button
      type="button"
      className={cn(
        "flex w-full items-center gap-3 rounded-2xl px-3 py-2 text-left text-sm text-slate-700 transition hover:bg-slate-100",
        className,
      )}
      onClick={() => {
        onSelect?.();
        setOpen(false);
      }}
    >
      {children}
    </button>
  );
}

export function DropdownMenuSeparator({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("my-2 h-px bg-slate-200", className)} {...props} />;
}
