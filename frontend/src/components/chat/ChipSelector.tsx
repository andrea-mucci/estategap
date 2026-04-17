"use client";

import { Button } from "@/components/ui/button";
import type { ChipItem } from "@/types/chat";

export function ChipSelector({
  chips,
  onSelect,
}: {
  chips: ChipItem[];
  onSelect: (chip: ChipItem) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {chips.map((chip) => (
        <Button
          aria-label={chip.label}
          key={chip.id}
          onClick={() => onSelect(chip)}
          size="sm"
          variant="outline"
        >
          {chip.label}
        </Button>
      ))}
    </div>
  );
}
