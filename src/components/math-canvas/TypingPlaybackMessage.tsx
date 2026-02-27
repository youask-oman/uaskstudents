"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import MarkdownMathContent from "@/components/math/MarkdownMathContent";
import { segmentsToMarkdown } from "@/lib/chat_final_playback";
import type { PlaybackSegment } from "./types";
import styles from "./MathCanvas.module.css";

type PlaybackStateResponse = {
  message_id: string;
  full_text: string;
  visible_len: number;
  speed_cps: number;
  is_complete: boolean;
  started_at_utc?: string | null;
};

interface TypingPlaybackMessageProps {
  messageId: string;
  fallbackContent: string;
  fallbackSegments?: PlaybackSegment[];
}

const isTypingEnabled = (): boolean => {
  return true;
};

const getMaxChars = (): number => {
  const raw = (process.env.NEXT_PUBLIC_CHAT_FINAL_TYPING_MAX_CHARS || "").trim();
  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || parsed <= 0) return 200000;
  return Math.floor(parsed);
};

const getTickMs = (): number => {
  const raw = (process.env.NEXT_PUBLIC_CHAT_FINAL_TYPING_TICK_MS || "").trim();
  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || parsed < 16) return 40;
  if (parsed > 120) return 40;
  return Math.floor(parsed);
};

const getCheckpointMs = (): number => {
  const raw = (process.env.NEXT_PUBLIC_CHAT_FINAL_TYPING_CHECKPOINT_MS || "").trim();
  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || parsed < 500) return 1500;
  return Math.floor(parsed);
};

const safeSliceByCodePoints = (codePoints: string[], count: number): string => {
  const clamped = Math.max(0, Math.min(codePoints.length, Math.floor(count)));
  return codePoints.slice(0, clamped).join("");
};

const hasBrokenInlineTextMath = (value: string): boolean => {
  const text = String(value || "").trim();
  if (!text) return false;
  if (/[A-Za-z]{2,}\([^)]*\)[A-Za-z]{2,}/.test(text)) return true;
  if (/,/.test(text) && /=/.test(text) && (text.match(/[A-Za-z]{4,}/g) || []).length >= 3) return true;
  return false;
};

const shouldUnwrapInlineProseMath = (value: string): boolean => {
  const text = String(value || "").trim();
  if (!text) return false;
  if (/\\text\{[^}]*\}/.test(text)) return true;
  const words = (text.match(/[A-Za-z]{3,}/g) || []).length;
  const hasEquationSignal = /[=,]/.test(text);
  return words >= 4 && hasEquationSignal;
};

const normalizeBrokenInlineTextMath = (value: string): string =>
  String(value || "")
    // Recover TAB-corrupted "\text" tokens before spacing normalization.
    .replace(/\text(?=[({])/g, "\\text")
    .replace(/\\text\{([^}]*)\}/g, "$1")
    .replace(/([A-Za-z]{2,})\(/g, "$1 (")
    .replace(/\)([A-Za-z]{2,})/g, ") $1")
    .replace(/,\s*(?=[A-Za-z]\([^)]*\)\s*=)/g, ",\n")
    .replace(/\s{2,}/g, " ")
    .trim();

const normalizeBrokenMathBlocksInMarkdown = (value: string): string => {
  let out = String(value || "");
  if (!out) return out;
  // Fix plain streamed lines too, not only math-delimited blocks.
  out = out
    .split("\n")
    .map((line) => (hasBrokenInlineTextMath(line) || /\text(?=[({])/.test(line) ? normalizeBrokenInlineTextMath(line) : line))
    .join("\n");
  out = out.replace(/\\\[\s*([\s\S]*?)\s*\\\]/g, (_full, inner: string) => {
    const body = String(inner || "").trim();
    if (!hasBrokenInlineTextMath(body)) return _full;
    return normalizeBrokenInlineTextMath(body);
  });
  out = out.replace(/\$\$\s*([\s\S]*?)\s*\$\$/g, (_full, inner: string) => {
    const body = String(inner || "").trim();
    if (!hasBrokenInlineTextMath(body)) return _full;
    return normalizeBrokenInlineTextMath(body);
  });
  out = out.replace(/\\\(\s*([^)]*?)\s*\\\)/g, (_full, inner: string) => {
    const body = String(inner || "").trim();
    if (!(hasBrokenInlineTextMath(body) || shouldUnwrapInlineProseMath(body))) return _full;
    return normalizeBrokenInlineTextMath(body);
  });
  return out;
};

const isEscaped = (text: string, index: number): boolean => {
  let count = 0;
  let cursor = index - 1;
  while (cursor >= 0 && text[cursor] === "\\") {
    count += 1;
    cursor -= 1;
  }
  return count % 2 === 1;
};

const clampToSafeMathBoundary = (text: string, desiredLen: number): number => {
  const totalLen = text.length;
  const target = Math.max(0, Math.min(totalLen, Math.floor(desiredLen)));
  if (target >= totalLen) return totalLen;
  if (target <= 0) return 0;

  let inlineParenOpen = false; // \( ... \) or ( ... )
  let blockBracketOpen = false; // \[ ... \] or [ ... ]
  let singleDollarOpen = false; // $ ... $
  let doubleDollarOpen = false; // $$ ... $$
  let lastSafe = 0;

  for (let i = 0; i < target; i += 1) {
    if (!isEscaped(text, i) && (text.startsWith("\\(", i) || text[i] === "(")) {
      if (!blockBracketOpen && !doubleDollarOpen && !singleDollarOpen) inlineParenOpen = true;
      if (text.startsWith("\\(", i)) i += 1;
    } else if (!isEscaped(text, i) && (text.startsWith("\\)", i) || text[i] === ")")) {
      if (inlineParenOpen) inlineParenOpen = false;
      if (text.startsWith("\\)", i)) i += 1;
    } else if (!isEscaped(text, i) && (text.startsWith("\\[", i) || text[i] === "[")) {
      if (!inlineParenOpen && !doubleDollarOpen && !singleDollarOpen) blockBracketOpen = true;
      if (text.startsWith("\\[", i)) i += 1;
    } else if (!isEscaped(text, i) && (text.startsWith("\\]", i) || text[i] === "]")) {
      if (blockBracketOpen) blockBracketOpen = false;
      if (text.startsWith("\\]", i)) i += 1;
    } else if (text[i] === "$" && !isEscaped(text, i) && !inlineParenOpen && !blockBracketOpen) {
      if (text[i + 1] === "$" && !isEscaped(text, i + 1)) {
        doubleDollarOpen = !doubleDollarOpen;
        i += 1;
      } else if (!doubleDollarOpen) {
        singleDollarOpen = !singleDollarOpen;
      }
    }

    if (!inlineParenOpen && !blockBracketOpen && !singleDollarOpen && !doubleDollarOpen) {
      lastSafe = i + 1;
    }
  }

  if (!inlineParenOpen && !blockBracketOpen && !singleDollarOpen && !doubleDollarOpen) {
    return target;
  }
  return lastSafe;
};

export default function TypingPlaybackMessage({ messageId, fallbackContent, fallbackSegments }: TypingPlaybackMessageProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fullText, setFullText] = useState<string>(fallbackContent || "");
  const [visibleLen, setVisibleLen] = useState<number>(0);
  const [speedCps, setSpeedCps] = useState<number>(160);
  const [isComplete, setIsComplete] = useState<boolean>(false);
  const lastAckLenRef = useRef<number>(0);
  const requestInFlightRef = useRef<boolean>(false);
  const startMsRef = useRef<number>(0);
  const baseVisibleRef = useRef<number>(0);
  const latestVisibleRef = useRef<number>(0);
  const latestCompleteRef = useRef<boolean>(false);

  const typingEnabled = isTypingEnabled();
  const maxChars = getMaxChars();
  const tickMs = getTickMs();
  const checkpointMs = getCheckpointMs();
  const segmentText = useMemo(
    () => (Array.isArray(fallbackSegments) && fallbackSegments.length > 0 ? segmentsToMarkdown(fallbackSegments) : ""),
    [fallbackSegments]
  );
  const effectiveFallbackText = segmentText || fallbackContent || "";
  const codePoints = useMemo(() => Array.from(fullText || ""), [fullText]);
  const totalLen = codePoints.length;
  const effectiveMaxChars = Math.max(12000, maxChars);
  const shouldBypassPlayback = !typingEnabled || totalLen > effectiveMaxChars;
  const segmentBoundaries = useMemo(() => {
    if (!segmentText) return [];
    const boundaries: number[] = [];
    let cursor = 0;
    const rawSegments = Array.isArray(fallbackSegments) ? fallbackSegments : [];
    rawSegments.forEach((seg) => {
      const block = segmentsToMarkdown([seg]);
      const len = Array.from(block).length;
      if (len <= 0) return;
      cursor += len;
      boundaries.push(cursor);
      cursor += 2; // paragraph separator used in markdown composer
    });
    return boundaries.filter((value) => value > 0);
  }, [segmentText, fallbackSegments]);

  const checkpoint = useCallback(async (nextVisible: number, complete: boolean) => {
    const clamped = Math.max(0, Math.min(totalLen, Math.floor(nextVisible)));
    if (clamped <= lastAckLenRef.current && !complete) return;
    if (requestInFlightRef.current) return;
    requestInFlightRef.current = true;
    try {
      await fetch("/api/v1/chat_final/playback_progress", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message_id: messageId,
          visible_len: clamped,
          is_complete: complete,
        }),
        keepalive: true,
      });
      lastAckLenRef.current = Math.max(lastAckLenRef.current, clamped);
    } catch {
      // Ignore checkpoint failures to keep UI smooth.
    } finally {
      requestInFlightRef.current = false;
    }
  }, [messageId, totalLen]);

  useEffect(() => {
    let canceled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/v1/chat_final/playback_state?message_id=${encodeURIComponent(messageId)}`, {
          cache: "no-store",
        });
        if (!res.ok) {
          throw new Error("failed_to_load_playback_state");
        }
        const data = (await res.json()) as PlaybackStateResponse;
        if (canceled) return;
        const serverText = typeof data.full_text === "string" ? data.full_text : "";
        // Prefer freshly synthesized client-side segment markdown so renderer fixes
        // (line wrapping / prose normalization) are reflected immediately.
        const text = effectiveFallbackText || serverText || "";
        const cpLen = Array.from(text).length;
        const serverVisible = Number.isFinite(Number(data.visible_len)) ? Number(data.visible_len) : 0;
        const serverComplete = Boolean(data.is_complete);
        const clampedVisible = serverComplete
          ? cpLen
          : Math.max(0, Math.min(cpLen, Math.floor(serverVisible)));
        setFullText(text);
        setVisibleLen(clampedVisible);
        const parsedSpeed = Number(data.speed_cps);
        const nextSpeed = Number.isFinite(parsedSpeed) && parsedSpeed > 0 ? Math.floor(parsedSpeed) : 160;
        setSpeedCps(Math.max(10, Math.min(220, nextSpeed)));
        setIsComplete(serverComplete || clampedVisible >= cpLen);
        lastAckLenRef.current = clampedVisible;
        baseVisibleRef.current = clampedVisible;
        startMsRef.current = Date.now();
      } catch {
        if (canceled) return;
        const text = effectiveFallbackText || "";
        const cpLen = Array.from(text).length;
        setFullText(text);
        setVisibleLen(cpLen);
        setIsComplete(true);
        setError("playback_unavailable");
        baseVisibleRef.current = cpLen;
        startMsRef.current = Date.now();
      } finally {
        if (!canceled) setLoading(false);
      }
    };
    void load();
    return () => {
      canceled = true;
    };
  }, [messageId, effectiveFallbackText]);

  useEffect(() => {
    if (loading) return;
    if (shouldBypassPlayback) {
      setVisibleLen(totalLen);
      setIsComplete(true);
      void checkpoint(totalLen, true);
      return;
    }
    if (isComplete || totalLen === 0) return;
    if (startMsRef.current <= 0) {
      startMsRef.current = Date.now();
      baseVisibleRef.current = visibleLen;
    }
    const timer = window.setInterval(() => {
      const elapsed = Math.max(0, (Date.now() - startMsRef.current) / 1000);
      const computed = baseVisibleRef.current + Math.floor(elapsed * speedCps);
      let next = Math.min(totalLen, computed);
      if (segmentBoundaries.length > 0) {
        const prev = latestVisibleRef.current;
        const boundary = segmentBoundaries.find((value) => value > prev && value < next);
        if (boundary) next = boundary;
      }
      setVisibleLen(next);
      if (next >= totalLen) {
        setIsComplete(true);
        void checkpoint(next, true);
      }
    }, tickMs);
    return () => window.clearInterval(timer);
  }, [checkpoint, loading, shouldBypassPlayback, isComplete, totalLen, speedCps, tickMs, segmentBoundaries, visibleLen]);

  useEffect(() => {
    latestVisibleRef.current = visibleLen;
  }, [visibleLen]);

  useEffect(() => {
    latestCompleteRef.current = isComplete || visibleLen >= totalLen;
  }, [isComplete, visibleLen, totalLen]);

  useEffect(() => {
    if (loading) return;
    const timer = window.setInterval(() => {
      void checkpoint(visibleLen, isComplete || visibleLen >= totalLen);
    }, checkpointMs);
    return () => window.clearInterval(timer);
  }, [checkpoint, checkpointMs, isComplete, loading, totalLen, visibleLen]);

  useEffect(() => {
    return () => {
      void checkpoint(latestVisibleRef.current, latestCompleteRef.current);
    };
  }, [checkpoint]);

  const renderedRaw = safeSliceByCodePoints(codePoints, clampToSafeMathBoundary(fullText, visibleLen));
  const rendered = normalizeBrokenMathBlocksInMarkdown(renderedRaw);
  const showSkip = !loading && !shouldBypassPlayback && !isComplete && visibleLen < totalLen;

  return (
    <div className={styles.chatBubbleAssistant}>
      {showSkip ? (
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 6 }}>
          <button
            type="button"
            className={styles.blockActionButton}
            onClick={() => {
              setVisibleLen(totalLen);
              setIsComplete(true);
              void checkpoint(totalLen, true);
            }}
          >
            Skip
          </button>
        </div>
      ) : null}
      {loading ? (
        <div style={{ opacity: 0.7 }}>Typing...</div>
      ) : (
        <MarkdownMathContent content={rendered} />
      )}
      {error ? <div style={{ marginTop: 6, fontSize: 11, opacity: 0.7 }}>Playback fallback active.</div> : null}
    </div>
  );
}
