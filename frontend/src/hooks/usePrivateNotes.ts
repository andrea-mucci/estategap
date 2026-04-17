"use client";

import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { patchCrmNotes } from "@/lib/api";

export function usePrivateNotes(listingId: string, initialNotes = "") {
  const { data: session } = useSession();
  const [notes, setNotes] = useState(initialNotes);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">(
    "idle",
  );

  useEffect(() => {
    setNotes(initialNotes);
  }, [initialNotes]);

  const mutation = useMutation({
    mutationFn: (nextNotes: string) =>
      patchCrmNotes(session?.accessToken, listingId, nextNotes),
    onError: () => {
      setSaveStatus("error");
    },
    onSuccess: (entry) => {
      setNotes(entry.notes);
      setSaveStatus("saved");
    },
  });

  useEffect(() => {
    if (notes === initialNotes) {
      return;
    }

    setSaveStatus("saving");
    const timer = window.setTimeout(() => {
      void mutation.mutateAsync(notes);
    }, 500);

    return () => {
      window.clearTimeout(timer);
    };
  }, [initialNotes, mutation, notes]);

  return {
    notes,
    saveStatus,
    setNotes,
  };
}
