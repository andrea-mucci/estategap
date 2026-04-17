"use client";

import { Check, Pencil, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { CriteriaField } from "@/types/chat";

type CriteriaSummaryCardProps = {
  fields: CriteriaField[];
  onConfirm: () => void;
  onUpdateField: (field: CriteriaField, value: string) => void;
};

export function CriteriaSummaryCard({
  fields,
  onConfirm,
  onUpdateField,
}: CriteriaSummaryCardProps) {
  const t = useTranslations("chat");
  const tCommon = useTranslations("common");

  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const editorRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setDrafts(
      fields.reduce<Record<string, string>>((accumulator, field) => {
        accumulator[field.key] = field.value;
        return accumulator;
      }, {}),
    );
  }, [fields]);

  useEffect(() => {
    if (!editingKey || !editorRef.current) {
      return;
    }

    const container = editorRef.current;
    const focusable = Array.from(
      container.querySelectorAll<HTMLElement>("input, select, button"),
    );

    focusable[0]?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setEditingKey(null);
        return;
      }

      if (event.key !== "Tab" || focusable.length === 0) {
        return;
      }

      const first = focusable[0];
      const last = focusable.at(-1);

      if (!first || !last) {
        return;
      }

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    container.addEventListener("keydown", onKeyDown);
    return () => {
      container.removeEventListener("keydown", onKeyDown);
    };
  }, [editingKey]);

  const commitField = (field: CriteriaField) => {
    const nextValue = `${drafts[field.key] ?? field.value}`.trim();
    onUpdateField(field, nextValue);
    setEditingKey(null);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("criteriaReady")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          {fields.map((field) => {
            const editing = editingKey === field.key;

            return (
              <div
                className="rounded-[24px] border border-slate-200 bg-slate-50 p-4"
                key={field.key}
              >
                <div className="mb-2 flex items-center justify-between gap-3">
                  <p className="text-sm font-medium text-slate-500">{field.label}</p>
                  {!editing ? (
                    <Button
                      aria-label={`Edit ${field.label}`}
                      onClick={() => setEditingKey(field.key)}
                      size="icon"
                      variant="ghost"
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                  ) : null}
                </div>

                {!editing ? (
                  <p className="text-base font-semibold text-slate-950">{field.value}</p>
                ) : (
                  <div className="space-y-3" ref={editorRef}>
                    {field.inputType === "select" ? (
                      <select
                        className="h-11 w-full rounded-2xl border border-slate-200 bg-white px-3"
                        onChange={(event) =>
                          setDrafts((current) => ({
                            ...current,
                            [field.key]: event.target.value,
                          }))
                        }
                        value={drafts[field.key] ?? field.value}
                      >
                        {(field.options ?? []).map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        className="h-11 w-full rounded-2xl border border-slate-200 bg-white px-3"
                        inputMode={field.inputType === "number" ? "numeric" : undefined}
                        onBlur={() => commitField(field)}
                        onChange={(event) =>
                          setDrafts((current) => ({
                            ...current,
                            [field.key]: event.target.value,
                          }))
                        }
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            commitField(field);
                          }
                        }}
                        value={drafts[field.key] ?? field.value}
                      />
                    )}

                    <div className="flex justify-end gap-2">
                      <Button
                        aria-label={tCommon("cancel")}
                        onClick={() => setEditingKey(null)}
                        size="icon"
                        variant="ghost"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                      <Button
                        aria-label={tCommon("save")}
                        onClick={() => commitField(field)}
                        size="icon"
                        variant="outline"
                      >
                        <Check className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <Button
          aria-label={t("searchAlert")}
          className="w-full sm:w-auto"
          onClick={onConfirm}
        >
          {t("searchAlert")}
        </Button>
      </CardContent>
    </Card>
  );
}
