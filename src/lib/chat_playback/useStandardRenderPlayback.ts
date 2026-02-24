"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { StandardPlaybackState, StandardRenderEvent, StandardPlaybackStep } from "@/lib/chat_playback/types";

const initialState = (): StandardPlaybackState => ({
  questionSummary: "",
  questionText: "",
  tasks: [],
  steps: [],
  finalAnswerText: "",
  finalAnswerLatex: "",
  finalAnswerValues: [],
  plot: null,
  pythonCode: "",
  verificationResults: [],
  quality: null,
  context: null,
  isTyping: false,
  isComplete: false,
  activeStepIndex: null,
});

const getNow = (): number => (typeof performance !== "undefined" ? performance.now() : Date.now());

const cloneSteps = (steps: StandardPlaybackStep[]): StandardPlaybackStep[] =>
  steps.map((step) => ({
    ...step,
    blocks: step.blocks.map((block) => ({ ...block })),
  }));

export function useStandardRenderPlayback(events: StandardRenderEvent[]) {
  const [state, setState] = useState<StandardPlaybackState>(initialState);
  const [playing, setPlaying] = useState(false);
  const [cursor, setCursor] = useState(0);

  const mountedRef = useRef(true);
  const timerRef = useRef<number | null>(null);
  const startedAtRef = useRef<number>(0);
  const pausedElapsedRef = useRef<number>(0);
  const playingRef = useRef(false);
  const cursorRef = useRef(0);

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
    if (mountedRef.current) {
      setPlaying((prev) => (prev === value ? prev : value));
    }
  }, []);

  const setCursorSafe = useCallback((value: number) => {
    cursorRef.current = value;
    if (mountedRef.current) {
      setCursor((prev) => (prev === value ? prev : value));
    }
  }, []);

  const applyEvent = useCallback((evt: StandardRenderEvent) => {
    if (!mountedRef.current) return;
    setState((prev) => {
      const next: StandardPlaybackState = { ...prev, steps: cloneSteps(prev.steps) };
      const payload = evt.payload || {};
      const stepIndex = Number(payload.step_index || 0);
      const blockId = String(payload.block_id || "");

      switch (evt.type) {
        case "MESSAGE_START":
          next.isTyping = true;
          return next;
        case "QUESTION_START":
          next.isTyping = true;
          return next;
        case "QUESTION_APPEND_SUMMARY":
          next.questionSummary = `${next.questionSummary}${String(payload.chunk || "")}`;
          next.isTyping = true;
          return next;
        case "QUESTION_APPEND_TEXT":
          next.questionText = `${next.questionText}${String(payload.chunk || "")}`;
          next.isTyping = true;
          return next;
        case "TASKS_SET":
          next.tasks = Array.isArray(payload.tasks)
            ? (payload.tasks as Array<{ task_index: number; task_label: string }>)
            : [];
          return next;
        case "STEP_START": {
          const title = String(payload.title || `Step ${stepIndex || 1}`);
          const existing = next.steps.find((s) => s.stepIndex === stepIndex);
          if (!existing) {
            next.steps.push({ stepIndex, title, blocks: [] });
          } else {
            existing.title = title;
          }
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
          block.text = `${block.text || ""}${String(payload.chunk || "")}`;
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
          block.latex = String(payload.latex || "");
          block.display = Boolean(payload.display);
          next.isTyping = true;
          return next;
        }
        case "STEP_END": {
          const step = next.steps.find((s) => s.stepIndex === stepIndex);
          if (step) step.done = true;
          next.activeStepIndex = null;
          return next;
        }
        case "FINAL_APPEND_TEXT":
          next.finalAnswerText = `${next.finalAnswerText}${String(payload.chunk || "")}`;
          next.isTyping = true;
          return next;
        case "FINAL_SET_MATH":
          next.finalAnswerLatex = String(payload.latex || "");
          next.isTyping = true;
          return next;
        case "FINAL_VALUES_SET":
          next.finalAnswerValues = Array.isArray(payload.values)
            ? (payload.values as StandardPlaybackState["finalAnswerValues"])
            : [];
          return next;
        case "PLOT_SHOW":
          next.plot = (payload.plot as Record<string, unknown>) || null;
          return next;
        case "PYTHON_CODE_SHOW":
          next.pythonCode = String(payload.code || "");
          return next;
        case "VERIFICATION_SET":
          next.verificationResults = Array.isArray(payload.task_results)
            ? (payload.task_results as Array<Record<string, unknown>>)
            : [];
          return next;
        case "QUALITY_SET":
          next.quality = (payload.quality as Record<string, unknown>) || null;
          return next;
        case "CONTEXT_SET":
          next.context = (payload.context as Record<string, unknown>) || null;
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
    if (!playingRef.current || !mountedRef.current) return;
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
    timerRef.current = window.setTimeout(flushUntilNow, wait > 0 ? Math.min(wait, 120) : 0);
  }, [applyEvent, clearTimer, normalized, setCursorSafe, setPlayingSafe]);

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

  const resume = useCallback(() => {
    if (playingRef.current) return;
    setPlayingSafe(true);
    startedAtRef.current = getNow();
    flushUntilNow();
  }, [flushUntilNow, setPlayingSafe]);

  const stop = useCallback(() => {
    clearTimer();
    setPlayingSafe(false);
    setCursorSafe(0);
    startedAtRef.current = 0;
    pausedElapsedRef.current = 0;
    if (mountedRef.current) {
      setState(initialState());
    }
  }, [clearTimer, setCursorSafe, setPlayingSafe]);

  const skipToEnd = useCallback(() => {
    clearTimer();
    for (let i = cursorRef.current; i < normalized.length; i += 1) {
      applyEvent(normalized[i]);
    }
    setCursorSafe(normalized.length);
    setPlayingSafe(false);
    if (mountedRef.current) {
      setState((prev) => ({ ...prev, isTyping: false, isComplete: true, activeStepIndex: null }));
    }
  }, [applyEvent, clearTimer, normalized, setCursorSafe, setPlayingSafe]);

  const replay = useCallback(() => {
    stop();
    if (!mountedRef.current) return;
    window.setTimeout(() => {
      if (!mountedRef.current) return;
      play();
    }, 0);
  }, [play, stop]);

  useEffect(() => {
    mountedRef.current = true;
    stop();
    if (normalized.length > 0) play();
    return () => {
      mountedRef.current = false;
      clearTimer();
    };
  }, [clearTimer, normalized, play, stop]);

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible" && playingRef.current) {
        flushUntilNow();
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [flushUntilNow]);

  return { state, playing, cursor, play, pause, resume, stop, skipToEnd, replay };
}

