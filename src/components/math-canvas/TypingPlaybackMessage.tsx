"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
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

  const checkpoint = async (nextVisible: number, complete: boolean) => {
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
  };

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
        const text = serverText || effectiveFallbackText || "";
        const cpLen = Array.from(text).length;
        const serverVisible = Number.isFinite(Number(data.visible_len)) ? Number(data.visible_len) : 0;
        const clampedVisible = Math.max(0, Math.min(cpLen, Math.floor(serverVisible)));
        setFullText(text);
        setVisibleLen(clampedVisible);
        const parsedSpeed = Number(data.speed_cps);
        const nextSpeed = Number.isFinite(parsedSpeed) && parsedSpeed > 0 ? Math.floor(parsedSpeed) : 160;
        setSpeedCps(Math.max(10, Math.min(220, nextSpeed)));
        setIsComplete(Boolean(data.is_complete) || clampedVisible >= cpLen);
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
  }, [loading, shouldBypassPlayback, isComplete, totalLen, speedCps, tickMs, segmentBoundaries]);

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
  }, [loading, visibleLen, isComplete, totalLen, checkpointMs]);

  useEffect(() => {
    return () => {
      void checkpoint(latestVisibleRef.current, latestCompleteRef.current);
    };
  }, []);

  const rendered = safeSliceByCodePoints(codePoints, visibleLen);
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
