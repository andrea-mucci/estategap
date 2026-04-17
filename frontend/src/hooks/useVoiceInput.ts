"use client";

import { useEffect, useEffectEvent, useRef, useState } from "react";

import type { VoiceInputState } from "@/types/chat";

type BrowserSpeechRecognitionResult = {
  isFinal: boolean;
  0: {
    transcript: string;
  };
};

type BrowserSpeechRecognitionEvent = {
  resultIndex: number;
  results: ArrayLike<BrowserSpeechRecognitionResult>;
};

type BrowserSpeechRecognitionErrorEvent = {
  error: string;
};

type BrowserSpeechRecognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onend: (() => void) | null;
  onerror: ((event: BrowserSpeechRecognitionErrorEvent) => void) | null;
  onresult: ((event: BrowserSpeechRecognitionEvent) => void) | null;
  start: () => void;
  stop: () => void;
};

type BrowserSpeechRecognitionConstructor = new () => BrowserSpeechRecognition;

const LOCALE_MAP: Record<string, string> = {
  de: "de-DE",
  el: "el-GR",
  en: "en-US",
  es: "es-ES",
  fr: "fr-FR",
  it: "it-IT",
  nl: "nl-NL",
  pl: "pl-PL",
  pt: "pt-PT",
  sv: "sv-SE",
};

function getSpeechRecognitionConstructor() {
  if (typeof window === "undefined") {
    return null;
  }

  const speechWindow = window as Window & {
    SpeechRecognition?: BrowserSpeechRecognitionConstructor;
    webkitSpeechRecognition?: BrowserSpeechRecognitionConstructor;
  };

  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition ?? null;
}

function toSpeechLocale(locale: string) {
  return LOCALE_MAP[locale] ?? locale;
}

export function useVoiceInput({
  locale,
  onTranscriptChange,
}: {
  locale: string;
  onTranscriptChange?: (value: string) => void;
}) {
  const [state, setState] = useState<VoiceInputState>("idle");
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [levels, setLevels] = useState<number[]>(Array.from({ length: 12 }, () => 0));
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const finalizedTranscriptRef = useRef("");

  const emitTranscript = useEffectEvent((value: string) => {
    onTranscriptChange?.(value);
  });

  const clearSilenceTimer = useEffectEvent(() => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  });

  const cleanupAudio = useEffectEvent(async () => {
    clearSilenceTimer();

    if (animationFrameRef.current != null) {
      window.cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    if (audioContextRef.current) {
      await audioContextRef.current.close().catch(() => undefined);
      audioContextRef.current = null;
    }

    analyserRef.current = null;
    mediaRecorderRef.current = null;
    setLevels(Array.from({ length: 12 }, () => 0));
  });

  const stopListening = useEffectEvent(() => {
    clearSilenceTimer();

    if (recognitionRef.current) {
      recognitionRef.current.stop();
      return;
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      setState("processing");
      mediaRecorderRef.current.stop();
    } else {
      void cleanupAudio();
      setState("idle");
    }
  });

  const scheduleSilenceTimeout = useEffectEvent(() => {
    clearSilenceTimer();
    silenceTimerRef.current = setTimeout(() => {
      stopListening();
    }, 2_000);
  });

  const updateLevels = useEffectEvent(() => {
    const analyser = analyserRef.current;

    if (!analyser) {
      return;
    }

    const samples = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(samples);

    const bars = Array.from({ length: 12 }, (_, index) => {
      const start = Math.floor((index * samples.length) / 12);
      const end = Math.floor(((index + 1) * samples.length) / 12);
      const slice = samples.slice(start, end);
      const average =
        slice.reduce((sum, value) => sum + value, 0) / Math.max(slice.length, 1);

      return Math.max(8, Math.round((average / 255) * 100));
    });

    const speaking = bars.some((value) => value > 14);
    if (speaking && state === "listening") {
      scheduleSilenceTimeout();
    }

    setLevels(bars);
    animationFrameRef.current = window.requestAnimationFrame(updateLevels);
  });

  const start = useEffectEvent(async () => {
    if (state === "listening" || state === "processing") {
      return;
    }

    setErrorMessage(null);
    setTranscript("");
    setInterimTranscript("");
    finalizedTranscriptRef.current = "";

    const recognitionConstructor = getSpeechRecognitionConstructor();
    const whisperAvailable =
      typeof window !== "undefined" &&
      typeof MediaRecorder !== "undefined" &&
      Boolean(navigator.mediaDevices?.getUserMedia);

    if (!recognitionConstructor && !whisperAvailable) {
      setState("error");
      setErrorMessage("unsupported");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      const audioContext = new AudioContext();
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      audioContext.createMediaStreamSource(stream).connect(analyser);
      audioContextRef.current = audioContext;
      analyserRef.current = analyser;
      animationFrameRef.current = window.requestAnimationFrame(updateLevels);
      scheduleSilenceTimeout();

      if (recognitionConstructor) {
        const recognition = new recognitionConstructor();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = toSpeechLocale(locale);

        recognition.onresult = (event) => {
          let finalChunk = "";
          let nextInterim = "";

          for (let index = event.resultIndex; index < event.results.length; index += 1) {
            const result = event.results[index];
            const alternative = result[0];

            if (!alternative) {
              continue;
            }

            if (result.isFinal) {
              finalChunk += alternative.transcript;
            } else {
              nextInterim += alternative.transcript;
            }
          }

          if (finalChunk.trim()) {
            finalizedTranscriptRef.current = `${finalizedTranscriptRef.current} ${finalChunk}`.trim();
            setTranscript(finalizedTranscriptRef.current);
          }

          const trimmedInterim = nextInterim.trim();
          setInterimTranscript(trimmedInterim);
          emitTranscript(`${finalizedTranscriptRef.current} ${trimmedInterim}`.trim());
          scheduleSilenceTimeout();
        };

        recognition.onerror = async (event) => {
          setState("error");
          setErrorMessage(
            event.error === "not-allowed" || event.error === "service-not-allowed"
              ? "permission"
              : "generic",
          );
          recognitionRef.current = null;
          await cleanupAudio();
        };

        recognition.onend = async () => {
          recognitionRef.current = null;
          setInterimTranscript("");
          emitTranscript(finalizedTranscriptRef.current);
          await cleanupAudio();
          setState(finalizedTranscriptRef.current ? "idle" : "idle");
        };

        recognitionRef.current = recognition;
        setState("listening");
        recognition.start();
        return;
      }

      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        try {
          setState("processing");

          const blob = new Blob(chunksRef.current, {
            type: mediaRecorder.mimeType || "audio/webm",
          });
          const formData = new FormData();
          formData.append("file", blob, "voice-input.webm");

          const response = await fetch("/api/whisper-proxy", {
            body: formData,
            method: "POST",
          });

          if (!response.ok) {
            throw new Error("whisper_failed");
          }

          const payload = (await response.json()) as { text?: string };
          const nextTranscript = `${payload.text ?? ""}`.trim();

          if (!nextTranscript) {
            setState("idle");
            await cleanupAudio();
            return;
          }

          finalizedTranscriptRef.current = nextTranscript;
          setTranscript(nextTranscript);
          emitTranscript(nextTranscript);
          await cleanupAudio();
          setState("idle");
        } catch {
          setState("error");
          setErrorMessage("generic");
          await cleanupAudio();
        }
      };

      setState("listening");
      mediaRecorder.start();
    } catch {
      setState("error");
      setErrorMessage("permission");
      await cleanupAudio();
    }
  });

  const stop = useEffectEvent(() => {
    stopListening();
  });

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
      void cleanupAudio();
    };
  }, [cleanupAudio]);

  return {
    errorMessage,
    interimTranscript,
    isSupported: Boolean(getSpeechRecognitionConstructor()),
    levels,
    start,
    state,
    stop,
    transcript,
    whisperAvailable:
      typeof window !== "undefined" &&
      typeof MediaRecorder !== "undefined" &&
      Boolean(navigator.mediaDevices?.getUserMedia),
  };
}
