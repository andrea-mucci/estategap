import * as React from "react";

import { cn } from "@/lib/utils";

export const Checkbox = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "h-4 w-4 rounded border-slate-300 text-teal-700 focus:ring-2 focus:ring-[var(--ring)]",
      className,
    )}
    type="checkbox"
    {...props}
  />
));

Checkbox.displayName = "Checkbox";

