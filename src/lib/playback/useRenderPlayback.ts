"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export type RenderEventType =
  | "MESSAGE_START"
  | "QUESTION_SET"
  | "STEP_START"
  | "BLOCK_APPEND_TEXT"
  | "BLOCK_SET_MATH"
  | "STEP_END"
  | "FINAL_ANSWER_SET"
  | "PLOT_SET"
  | "PYTHON_CODE_SET"
  | "MESSAGE_END";

export interface RenderEvent {
  id: string;
  at_ms: number;
  type: RenderEventType;
  payload: Record<string, unknown>;
}

export interface RenderProfile {
  text_cps?: number;
  chunk_size_chars?: number;
  jitter_ms?: number;
  step_pause_ms?: number;
  math_drop_delay_ms?: number;
  plot_delay_ms?: number;
  code_delay_ms?: number;
  seed?: string;
  profile_version?: string;
}

export interface PlaybackBlock {
  id: string;
  kind: "text" | "math";
  text?: string;
  latex?: string;
  display?: boolean;
}

export interface PlaybackStep {
  stepIndex: number;
  title: string;
  blocks: PlaybackBlock[];
  done?: boolean;
}

export interface PlaybackState {
  questionText: string;
  steps: PlaybackStep[];
  finalAnswer: Record<string, unknown> | null;
  plot: Record<string, unknown> | null;
  pythonCode: string;
  isTyping: boolean;
  isComplete: boolean;
  activeStepIndex: number | null;
}

const initialState = (): PlaybackState => ({
  questionText: "",
  steps: [],
  finalAnswer: null,
  plot: null,
  pythonCode: "",
  isTyping: false,
  isComplete: false,
  activeStepIndex: null,
});

const getNow = (): number => (typeof performance !== "undefined" ? performance.now() : Date.now());

const decodeEscapedMathText = (value: string): string => {
  let text = String(value || "");
  if (!text) return "";
  text = text.replace(/\\u\{([0-9a-fA-F]+)\}/g, (_, hex: string) => {
    try {
      return String.fromCodePoint(parseInt(hex, 16));
    } catch {
      return _;
    }
  });
  text = text.replace(/\\u([0-9a-fA-F]{4})/g, (_, hex: string) => {
    try {
      return String.fromCharCode(parseInt(hex, 16));
    } catch {
      return _;
    }
  });
  text = text
    .replace(/\\n/g, "\n")
    .replace(/\\r/g, "\r")
    .replace(/\\t/g, "\t")
    .replace(/\\\\([a-zA-Z]+)/g, "\\$1");
  return text;
};

const decodeDeep = (value: unknown): unknown => {
  if (typeof value === "string") return decodeEscapedMathText(value);
  if (Array.isArray(value)) return value.map((item) => decodeDeep(item));
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = decodeDeep(v);
    }
    return out;
  }
  return value;
};

export function useRenderPlayback(events: RenderEvent[]) {
  const [state, setState] = useState<PlaybackState>(initialState);
  const [playing, setPlaying] = useState(false);
  const [cursor, setCursor] = useState(0);
  const timerRef = useRef<number | null>(null);
  const startedAtRef = useRef<number>(0);
  const pausedElapsedRef = useRef<number>(0);
  const playingRef = useRef<boolean>(false);
  const cursorRef = useRef<number>(0);
  const flushUntilNowRef = useRef<() => void>(() => undefined);

  const normalized = useMemo(
    () => [...events].sort((a, b) => Number(a.at_ms || 0) - Number(b.at_ms || 0)),
    [events]
  );

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const setPlayingSafe = useCallback((value: boolean) => {
    playingRef.current = value;
    setPlaying((prev) => (prev === value ? prev : value));
  }, []);

  const setCursorSafe = useCallback((value: number) => {
    cursorRef.current = value;
    setCursor((prev) => (prev === value ? prev : value));
  }, []);

  const applyEvent = useCallback((evt: RenderEvent) => {
    setState((prev) => {
      const next: PlaybackState = {
        ...prev,
        steps: prev.steps.map((s) => ({ ...s, blocks: s.blocks.map((b) => ({ ...b })) })),
      };
      const p = evt.payload || {};
      const stepIndex = Number(p.step_index || 0);
      const blockId = String(p.block_id || "");
      switch (evt.type) {
        case "MESSAGE_START":
          next.isTyping = true;
          return next;
        case "QUESTION_SET":
          next.questionText = decodeEscapedMathText(String(p.text || ""));
          return next;
        case "STEP_START": {
          const title = String(p.title || `Step ${stepIndex}`);
          const existing = next.steps.find((s) => s.stepIndex === stepIndex);
          if (!existing) next.steps.push({ stepIndex, title, blocks: [] });
          next.activeStepIndex = stepIndex || null;
          next.isTyping = true;
          return next;
        }
        case "BLOCK_APPEND_TEXT": {
          const step = next.steps.find((s) => s.stepIndex === stepIndex);
          if (!step) return next;
          let block = step.blocks.find((b) => b.id === blockId);
          if (!block) {
            block = { id: blockId, kind: "text", text: "" };
            step.blocks.push(block);
          }
          block.kind = "text";
          block.text = `${block.text || ""}${decodeEscapedMathText(String(p.chunk || ""))}`;
          next.isTyping = true;
          return next;
        }
        case "BLOCK_SET_MATH": {
          const step = next.steps.find((s) => s.stepIndex === stepIndex);
          if (!step) return next;
          let block = step.blocks.find((b) => b.id === blockId);
          if (!block) {
            block = { id: blockId, kind: "math" };
            step.blocks.push(block);
          }
          block.kind = "math";
          block.latex = decodeEscapedMathText(String(p.latex || ""));
          block.display = Boolean(p.display);
          next.isTyping = true;
          return next;
        }
        case "STEP_END": {
          const step = next.steps.find((s) => s.stepIndex === stepIndex);
          if (step) step.done = true;
          next.activeStepIndex = null;
          return next;
        }
        case "FINAL_ANSWER_SET":
          next.finalAnswer = decodeDeep(p) as Record<string, unknown>;
          return next;
        case "PLOT_SET":
          next.plot = p;
          return next;
        case "PYTHON_CODE_SET":
          next.pythonCode = String(p.code || "");
          return next;
        case "MESSAGE_END":
          next.isTyping = false;
          next.isComplete = true;
          next.activeStepIndex = null;
          return next;
        default:
          return next;
      }
    });
  }, []);

  const flushUntilNow = useCallback(() => {
    if (!playingRef.current) return;
    const elapsed = pausedElapsedRef.current + (getNow() - startedAtRef.current);
    let i = cursorRef.current;
    while (i < normalized.length && Number(normalized[i].at_ms || 0) <= elapsed) {
      applyEvent(normalized[i]);
      i += 1;
    }
    if (i !== cursorRef.current) setCursorSafe(i);
    if (i >= normalized.length) {
      clearTimer();
      setPlayingSafe(false);
      return;
    }
    const nextAt = Number(normalized[i].at_ms || 0);
    const wait = Math.max(0, nextAt - elapsed);
    clearTimer();
    timerRef.current = window.setTimeout(() => flushUntilNowRef.current(), wait > 0 ? Math.min(wait, 120) : 0);
  }, [applyEvent, clearTimer, normalized, setCursorSafe, setPlayingSafe]);
  useEffect(() => {
    flushUntilNowRef.current = flushUntilNow;
  }, [flushUntilNow]);

  const play = useCallback(() => {
    if (normalized.length === 0) return;
    setPlayingSafe(true);
    startedAtRef.current = getNow();
    flushUntilNow();
  }, [flushUntilNow, normalized.length, setPlayingSafe]);

  const pause = useCallback(() => {
    if (!playingRef.current) return;
    pausedElapsedRef.current += getNow() - startedAtRef.current;
    setPlayingSafe(false);
    clearTimer();
  }, [clearTimer, setPlayingSafe]);

  const stop = useCallback(() => {
    clearTimer();
    setPlayingSafe(false);
    setCursorSafe(0);
    startedAtRef.current = 0;
    pausedElapsedRef.current = 0;
    setState(initialState());
  }, [clearTimer, setCursorSafe, setPlayingSafe]);

  const resume = useCallback(() => {
    if (playingRef.current) return;
    setPlayingSafe(true);
    startedAtRef.current = getNow();
    flushUntilNow();
  }, [flushUntilNow, setPlayingSafe]);

  const skipToEnd = useCallback(() => {
    clearTimer();
    for (let i = cursorRef.current; i < normalized.length; i += 1) {
      applyEvent(normalized[i]);
    }
    setCursorSafe(normalized.length);
    setPlayingSafe(false);
    setState((prev) => ({ ...prev, isTyping: false, isComplete: true }));
  }, [applyEvent, clearTimer, normalized, setCursorSafe, setPlayingSafe]);

  const replay = useCallback(() => {
    stop();
    setTimeout(() => {
      play();
    }, 0);
  }, [play, stop]);

  useEffect(() => {
    clearTimer();
    queueMicrotask(() => {
      setState(initialState());
      setCursorSafe(0);
      setPlayingSafe(false);
      startedAtRef.current = 0;
      pausedElapsedRef.current = 0;
      if (normalized.length > 0) {
        setPlayingSafe(true);
        startedAtRef.current = getNow();
        flushUntilNowRef.current();
      }
    });
    return () => clearTimer();
  }, [clearTimer, normalized, setCursorSafe, setPlayingSafe]);

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible" && playingRef.current) flushUntilNow();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [flushUntilNow]);

  return { state, playing, cursor, play, pause, resume, stop, skipToEnd, replay };
}
