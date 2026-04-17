"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

type DialogContextValue = {
  open: boolean;
  setOpen: (value: boolean) => void;
};

const DialogContext = React.createContext<DialogContextValue | null>(null);

function useDialogContext() {
  const context = React.useContext(DialogContext);

  if (!context) {
    throw new Error("Dialog components must be used within Dialog");
  }

  return context;
}

export function Dialog({
  children,
  open,
  onOpenChange,
}: {
  children: React.ReactNode;
  open?: boolean;
  onOpenChange?: (value: boolean) => void;
}) {
  const [internalOpen, setInternalOpen] = React.useState(false);
  const value = open ?? internalOpen;
  const setValue = onOpenChange ?? setInternalOpen;

  return (
    <DialogContext.Provider value={{ open: value, setOpen: setValue }}>
      {children}
    </DialogContext.Provider>
  );
}

export function DialogTrigger({
  asChild,
  children,
}: {
  asChild?: boolean;
  children: React.ReactNode;
}) {
  const { open, setOpen } = useDialogContext();

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

export function DialogContent({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  const { open, setOpen } = useDialogContext();

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/40 px-4 backdrop-blur-sm">
      <button
        aria-label="Close dialog"
        className="absolute inset-0"
        onClick={() => setOpen(false)}
        type="button"
      />
      <div
        className={cn(
          "relative z-10 w-full max-w-lg rounded-[28px] bg-white p-6 shadow-2xl",
          className,
        )}
      >
        {children}
      </div>
    </div>
  );
}
