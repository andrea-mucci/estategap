"use client";

import { useEffect, useState } from "react";

import { Input } from "@/components/ui/input";

type DualRangeFieldProps = {
  formatValue: (value: number) => string;
  label: string;
  max: number;
  min: number;
  onCommit: (value: [number | null, number | null]) => void;
  step: number;
  value: [number | null | undefined, number | null | undefined];
};

export function DualRangeField({
  formatValue,
  label,
  max,
  min,
  onCommit,
  step,
  value,
}: DualRangeFieldProps) {
  const [draft, setDraft] = useState<[number, number]>([
    value[0] ?? min,
    value[1] ?? max,
  ]);

  useEffect(() => {
    setDraft([value[0] ?? min, value[1] ?? max]);
  }, [max, min, value]);

  function commit(nextDraft: [number, number]) {
    const nextMin = nextDraft[0] <= min ? null : nextDraft[0];
    const nextMax = nextDraft[1] >= max ? null : nextDraft[1];
    onCommit([nextMin, nextMax]);
  }

  function updateIndex(index: 0 | 1, rawValue: number) {
    setDraft((current) => {
      const next = [...current] as [number, number];
      next[index] = rawValue;

      if (index === 0) {
        next[0] = Math.min(rawValue, current[1]);
      } else {
        next[1] = Math.max(rawValue, current[0]);
      }

      return next;
    });
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
          <span>{label}</span>
          <span>{`${formatValue(draft[0])} — ${formatValue(draft[1])}`}</span>
        </div>
        <div className="relative px-1">
          <div className="absolute left-1 right-1 top-1/2 h-1 -translate-y-1/2 rounded-full bg-slate-200" />
          <div
            className="pointer-events-none absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-teal-500"
            style={{
              left: `${((draft[0] - min) / (max - min)) * 100}%`,
              right: `${100 - ((draft[1] - min) / (max - min)) * 100}%`,
            }}
          />
          <input
            aria-label={`${label} minimum`}
            className="pointer-events-none absolute inset-0 h-6 w-full appearance-none bg-transparent [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:bg-teal-700"
            max={max}
            min={min}
            onChange={(event) => updateIndex(0, Number(event.target.value))}
            onKeyUp={() => commit(draft)}
            onMouseUp={() => commit(draft)}
            onTouchEnd={() => commit(draft)}
            step={step}
            type="range"
            value={draft[0]}
          />
          <input
            aria-label={`${label} maximum`}
            className="pointer-events-none relative h-6 w-full appearance-none bg-transparent [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:bg-teal-700"
            max={max}
            min={min}
            onChange={(event) => updateIndex(1, Number(event.target.value))}
            onKeyUp={() => commit(draft)}
            onMouseUp={() => commit(draft)}
            onTouchEnd={() => commit(draft)}
            step={step}
            type="range"
            value={draft[1]}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Input
          inputMode="numeric"
          onBlur={() => commit(draft)}
          onChange={(event) => updateIndex(0, Number(event.target.value || min))}
          value={draft[0]}
        />
        <Input
          inputMode="numeric"
          onBlur={() => commit(draft)}
          onChange={(event) => updateIndex(1, Number(event.target.value || max))}
          value={draft[1]}
        />
      </div>
    </div>
  );
}

