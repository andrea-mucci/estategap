"use client";

import * as React from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

type AccordionType = "single" | "multiple";

type AccordionContextValue = {
  isOpen: (value: string) => boolean;
  toggle: (value: string) => void;
};

const AccordionContext = React.createContext<AccordionContextValue | null>(null);
const AccordionItemContext = React.createContext<string | null>(null);

function useAccordionContext() {
  const context = React.useContext(AccordionContext);
  if (!context) {
    throw new Error("Accordion components must be used inside Accordion.");
  }
  return context;
}

function useAccordionItemValue() {
  const value = React.useContext(AccordionItemContext);
  if (!value) {
    throw new Error("Accordion item components must be used inside AccordionItem.");
  }
  return value;
}

export function Accordion({
  children,
  className,
  type,
}: {
  children: React.ReactNode;
  className?: string;
  type: AccordionType;
}) {
  const [openValues, setOpenValues] = React.useState<string[]>([]);

  const value = React.useMemo<AccordionContextValue>(
    () => ({
      isOpen: (itemValue) => openValues.includes(itemValue),
      toggle: (itemValue) => {
        setOpenValues((current) => {
          if (type === "single") {
            return current[0] === itemValue ? [] : [itemValue];
          }

          return current.includes(itemValue)
            ? current.filter((value) => value !== itemValue)
            : [...current, itemValue];
        });
      },
    }),
    [openValues, type],
  );

  return (
    <AccordionContext.Provider value={value}>
      <div className={cn("space-y-3", className)}>{children}</div>
    </AccordionContext.Provider>
  );
}

export function AccordionItem({
  children,
  className,
  value,
}: {
  children: React.ReactNode;
  className?: string;
  value: string;
}) {
  return (
    <AccordionItemContext.Provider value={value}>
      <div className={cn("rounded-[24px] border border-white/70 bg-white/80", className)}>
        {children}
      </div>
    </AccordionItemContext.Provider>
  );
}

export function AccordionTrigger({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const { isOpen, toggle } = useAccordionContext();
  const value = useAccordionItemValue();
  const open = isOpen(value);

  return (
    <button
      className={cn(
        "flex w-full items-center justify-between gap-4 px-5 py-4 text-left text-base font-semibold text-slate-950",
        className,
      )}
      onClick={() => toggle(value)}
      type="button"
    >
      <span>{children}</span>
      <ChevronDown className={cn("h-5 w-5 text-slate-500 transition", open && "rotate-180")} />
    </button>
  );
}

export function AccordionContent({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const { isOpen } = useAccordionContext();
  const value = useAccordionItemValue();

  if (!isOpen(value)) {
    return null;
  }

  return <div className={cn("px-5 pb-5 text-sm leading-7 text-slate-600", className)}>{children}</div>;
}
