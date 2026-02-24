"use client";

import { useEffect, useMemo, useState } from "react";
import CodeBlock from "@/components/code/CodeBlock";
import PlotCard from "@/components/plot/PlotCard";
import BlockRenderer from "@/components/solve/BlockRenderer";
import TypingIndicator from "@/components/solve/TypingIndicator";
import UnifiedMathRenderer from "@/components/math/UnifiedMathRenderer";
import MarkdownMathContent from "@/components/math/MarkdownMathContent";
import { buildStandardEventsFromStructuredData } from "@/lib/chat_playback/buildStandardEventsFromStructured";
import { buildRenderModel } from "@/lib/chat_playback/buildRenderModel";
import { convertBackendRenderEventsToStandard } from "@/lib/chat_playback/convertBackendRenderEvents";
import { useStandardRenderPlayback } from "@/lib/chat_playback/useStandardRenderPlayback";
import type { StandardRenderEvent } from "@/lib/chat_playback/types";

interface Props {
  structuredData: Record<string, unknown>;
  attemptId: string;
  playbackMessageId?: string | null;
  onOutlineItemsChange?: (items: Array<{ id: string; label: string; tag: string }>) => void;
}

const INSTANT_PREF_KEY = "chat_standard_show_instantly";
const doneKey = (attemptId: string) => `chat_standard_playback_done_${attemptId}`;

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" ? (value as Record<string, unknown>) : null;

const asString = (value: unknown): string => (typeof value === "string" ? value : value == null ? "" : String(value));

const hasNonEmptyValue = (value: unknown): boolean => {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value as Record<string, unknown>).length > 0;
  return true;
};

export default function StandardChatSolvePlayer({
  structuredData,
  attemptId,
  playbackMessageId,
  onOutlineItemsChange,
}: Props) {
  const [remoteEvents, setRemoteEvents] = useState<StandardRenderEvent[] | null>(null);
  const [showTasks, setShowTasks] = useState(false);
  const [showPython, setShowPython] = useState(false);
  const [showVerification, setShowVerification] = useState(false);
  const [showQuality, setShowQuality] = useState(false);
  const [showContext, setShowContext] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [showInstantly, setShowInstantly] = useState(false);

  const renderModel = useMemo(() => buildRenderModel(structuredData), [structuredData]);
  const primaryItem = renderModel.items[0] || null;
  const isRefusal = Boolean(primaryItem?.refusal?.is_refusal);
  const classificationBadges = useMemo(() => {
    if (!primaryItem) return [];
    const badges: string[] = [];
    if (primaryItem.classification.domain) badges.push(primaryItem.classification.domain);
    badges.push(...primaryItem.classification.detected_tasks.slice(0, 10));
    return badges;
  }, [primaryItem]);

  const fallbackEvents = useMemo(
    () => buildStandardEventsFromStructuredData(structuredData, attemptId),
    [structuredData, attemptId]
  );
  const events = remoteEvents && remoteEvents.length > 0 ? remoteEvents : fallbackEvents;
  const { state, replay, skipToEnd } = useStandardRenderPlayback(events);

  useEffect(() => {
    let cancelled = false;
    const messageId = asString(playbackMessageId).trim();
    if (!messageId) {
      setRemoteEvents(null);
      return () => {
        cancelled = true;
      };
    }

    const run = async () => {
      try {
        const response = await fetch(
          `/api/v1/chat_final/playback_state?message_id=${encodeURIComponent(messageId)}`,
          { cache: "no-store" }
        );
        if (!response.ok) throw new Error("playback_state_unavailable");
        const body = (await response.json()) as { render_events?: unknown[] };
        const converted = convertBackendRenderEventsToStandard(
          Array.isArray(body?.render_events) ? (body.render_events as unknown[]) : []
        );
        if (!cancelled) setRemoteEvents(converted.length > 0 ? converted : null);
      } catch {
        if (!cancelled) setRemoteEvents(null);
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [playbackMessageId]);

  useEffect(() => {
    const pref = typeof window !== "undefined" ? window.localStorage.getItem(INSTANT_PREF_KEY) : null;
    const parsed = pref === "1";
    setShowInstantly(parsed);
    if (parsed) {
      skipToEnd();
      return;
    }
    if (typeof window !== "undefined") {
      const completed = window.localStorage.getItem(doneKey(attemptId)) === "1";
      if (completed) skipToEnd();
    }
  }, [attemptId, skipToEnd]);

  useEffect(() => {
    if (!state.isComplete || typeof window === "undefined") return;
    window.localStorage.setItem(doneKey(attemptId), "1");
  }, [attemptId, state.isComplete]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(INSTANT_PREF_KEY, showInstantly ? "1" : "0");
    if (showInstantly) skipToEnd();
  }, [showInstantly, skipToEnd]);

  useEffect(() => {
    if (!onOutlineItemsChange) return;
    const items: Array<{ id: string; label: string; tag: string }> = [];
    items.push({ id: "std-question", label: "Question", tag: "QUESTION" });
    if (isRefusal) {
      items.push({ id: "std-refusal", label: "Refusal", tag: "REFUSAL" });
      onOutlineItemsChange(items);
      return;
    }
    state.steps.forEach((step, idx) => {
      const active = state.activeStepIndex === step.stepIndex;
      const tag = active ? "ACTIVE" : step.done ? "STEP" : "PENDING";
      items.push({ id: `std-step-${step.stepIndex}`, label: step.title || `Step ${idx + 1}`, tag });
    });
    if (hasNonEmptyValue(state.finalAnswerText) || hasNonEmptyValue(state.finalAnswerLatex) || state.finalAnswerValues.length > 0) {
      items.push({ id: "std-final-answer", label: "Final Answer", tag: "FINAL" });
    }
    if (state.plot) items.push({ id: "std-plot", label: "Plot", tag: "PLOT" });
    if (hasNonEmptyValue(state.pythonCode)) items.push({ id: "std-python", label: "Python Code", tag: "CODE" });
    onOutlineItemsChange(items);
  }, [
    isRefusal,
    onOutlineItemsChange,
    state.activeStepIndex,
    state.finalAnswerLatex,
    state.finalAnswerText,
    state.finalAnswerValues.length,
    state.plot,
    state.pythonCode,
    state.steps,
  ]);

  const contextEntries = useMemo(() => {
    const ctx = asRecord(state.context);
    if (!ctx) return [];
    return Object.entries(ctx).filter(([, value]) => hasNonEmptyValue(value));
  }, [state.context]);

  const plotRecipe = asRecord(state.plot)?.recipe;
  const showPlot = Boolean(asRecord(state.plot)?.should_visualize) && Boolean(plotRecipe);
  const plotAttemptId = asString(asRecord(state.plot)?.attempt_id).trim() || attemptId;
  const detailEntries = useMemo(() => {
    if (!primaryItem) return [] as Array<[string, string]>;
    const rows: Array<[string, string]> = [];
    const push = (label: string, value: unknown) => {
      if (!hasNonEmptyValue(value)) return;
      rows.push([label, asString(value).trim()]);
    };
    push("Question ID", (primaryItem.raw_non_null as Record<string, unknown>)?.question_id);
    push("Domain Mode", (primaryItem.raw_non_null as Record<string, unknown>)?.domain_mode);
    push("Task Count", (primaryItem.raw_non_null as Record<string, unknown>)?.task_count);
    return rows;
  }, [primaryItem]);
  const finalValues = state.finalAnswerValues.length > 0
    ? state.finalAnswerValues
    : state.verificationResults.map((row, idx) => ({
        key: asString(row.task_label) || `task_${idx + 1}`,
        text: asString(row.result_text) || asString(row.result_latex) || "",
        latex: null,
        number: null,
        unit: null,
      }));

  return (
    <div style={{ padding: 0, overflowY: "auto", width: "100%", minHeight: "calc(100vh - 120px)" }}>
      <div
        style={{
          gap: 12,
          width: "100%",
          maxWidth: "100%",
          background: "transparent",
          display: "flex",
          flexDirection: "column",
          padding: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", letterSpacing: "0.08em" }}>STANDARD</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <label style={{ fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
              <input type="checkbox" checked={showInstantly} onChange={(e) => setShowInstantly(e.target.checked)} />
              Show instantly
            </label>
            <button
              type="button"
              onClick={() => {
                if (typeof window !== "undefined") window.localStorage.removeItem(doneKey(attemptId));
                replay();
              }}
              style={{ border: "1px solid #cbd5e1", borderRadius: 6, padding: "3px 10px", fontSize: 12 }}
            >
              Replay
            </button>
          </div>
        </div>

        <section id="std-question" style={{ borderBottom: "1px solid #e2e8f0", paddingBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, opacity: 0.72, marginBottom: 8 }}>QUESTION Q1</div>
          {classificationBadges.length > 0 ? (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
              {classificationBadges.map((badge, idx) => (
                <span
                  key={`badge-${idx}`}
                  style={{
                    border: "1px solid #bfdbfe",
                    color: "#1d4ed8",
                    background: "#eff6ff",
                    borderRadius: 999,
                    padding: "2px 8px",
                    fontSize: 11,
                    fontWeight: 600,
                  }}
                >
                  {badge}
                </span>
              ))}
            </div>
          ) : null}
          {state.questionSummary.trim() ? (
            <div style={{ marginBottom: 8, color: "#475569", fontSize: 14 }}>
              <MarkdownMathContent content={state.questionSummary} />
            </div>
          ) : null}
          {state.questionText.trim() ? (
            <UnifiedMathRenderer content={state.questionText} mode="prose" />
          ) : (
            <div style={{ fontSize: 13, color: "#64748b" }}>Preparing question...</div>
          )}
          {state.tasks.length > 0 ? (
            <details style={{ marginTop: 12 }} open={showTasks} onToggle={(e) => setShowTasks((e.target as HTMLDetailsElement).open)}>
              <summary style={{ cursor: "pointer", fontSize: 12, fontWeight: 700, color: "#334155" }}>
                Tasks ({state.tasks.length})
              </summary>
              <ul style={{ marginTop: 8, paddingInlineStart: 18 }}>
                {state.tasks.map((task) => (
                  <li key={`task-${task.task_index}`} style={{ marginBottom: 4, fontSize: 13 }}>
                    <a href={`#std-step-${task.task_index}`} style={{ color: "#1d4ed8", textDecoration: "none" }}>
                      {task.task_label}
                    </a>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </section>

        {isRefusal ? (
          <section id="std-refusal" style={{ border: "1px solid #fecaca", background: "#fff1f2", borderRadius: 10, padding: 12 }}>
            <div style={{ fontSize: 11, fontWeight: 700, opacity: 0.78, marginBottom: 8 }}>REFUSAL</div>
            {primaryItem?.refusal?.refusal_code ? (
              <div style={{ fontSize: 13, marginBottom: 6 }}>
                <strong>Code:</strong> {primaryItem.refusal.refusal_code}
              </div>
            ) : null}
            <div style={{ fontSize: 13 }}>{primaryItem?.refusal?.refusal_message || "This request was refused."}</div>
          </section>
        ) : null}

        {!isRefusal ? state.steps.map((step) => (
              <section
                key={`step-${step.stepIndex}`}
                id={`std-step-${step.stepIndex}`}
                style={{
                  borderBottom: "1px solid #e2e8f0",
                  padding: "10px 0 12px",
                  boxShadow: "none",
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 700, opacity: 0.78, marginBottom: 8 }}>{step.title}</div>
                <div>
                  {step.blocks.map((block) => (
                    <BlockRenderer key={block.id} block={block} />
                  ))}
                </div>
              </section>
            )) : null}

        {!isRefusal && (hasNonEmptyValue(state.finalAnswerText) || hasNonEmptyValue(state.finalAnswerLatex) || finalValues.length > 0) ? (
          <section id="std-final-answer" style={{ border: "1px solid #bbf7d0", background: "#f0fdf4", borderRadius: 10, padding: 12, marginTop: 6 }}>
            <div style={{ fontSize: 11, fontWeight: 700, opacity: 0.78, marginBottom: 8 }}>FINAL ANSWER</div>
            {state.finalAnswerText ? <MarkdownMathContent content={state.finalAnswerText} /> : null}
            {state.finalAnswerLatex ? <UnifiedMathRenderer content={state.finalAnswerLatex} mode="block" /> : null}
            {finalValues.length > 0 ? (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
                {finalValues.map((entry, idx) => {
                  const value = entry.text || entry.latex || (typeof entry.number === "number" ? String(entry.number) : null) || "";
                  return (
                    <span
                      key={`value-${idx}`}
                      style={{
                        border: "1px solid #86efac",
                        borderRadius: 999,
                        padding: "4px 10px",
                        fontSize: 12,
                        background: "#ffffff",
                        color: "#166534",
                      }}
                    >
                      {entry.key || "value"}: {value}
                      {entry.unit ? ` ${entry.unit}` : ""}
                    </span>
                  );
                })}
              </div>
            ) : null}
          </section>
        ) : null}

        {!isRefusal && showPlot ? (
          <section id="std-plot" style={{ borderTop: "1px solid #e2e8f0", paddingTop: 12 }}>
            <div style={{ fontSize: 11, fontWeight: 700, opacity: 0.78, marginBottom: 8 }}>PLOT</div>
            <PlotCard plot={state.plot} attemptId={plotAttemptId} playbackVisible={true} />
          </section>
        ) : null}

        {!isRefusal && hasNonEmptyValue(state.pythonCode) ? (
          <section id="std-python" style={{ borderTop: "1px solid #e2e8f0", paddingTop: 12 }}>
            <details open={showPython} onToggle={(e) => setShowPython((e.target as HTMLDetailsElement).open)}>
              <summary style={{ cursor: "pointer", fontSize: 12, fontWeight: 700, color: "#334155" }}>Python code</summary>
              <div style={{ marginTop: 8 }}>
                <CodeBlock code={state.pythonCode} language="python" />
              </div>
            </details>
          </section>
        ) : null}

        {!isRefusal && state.verificationResults.length > 0 ? (
          <section style={{ borderTop: "1px solid #e2e8f0", paddingTop: 12 }}>
            <details open={showVerification} onToggle={(e) => setShowVerification((e.target as HTMLDetailsElement).open)}>
              <summary style={{ cursor: "pointer", fontSize: 12, fontWeight: 700, color: "#334155" }}>
                Verification / Checklist
              </summary>
              <div style={{ marginTop: 8, display: "grid", gap: 8 }}>
                {state.verificationResults.map((row, idx) => (
                  <div key={`verification-${idx}`} style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 8 }}>
                    <div style={{ fontSize: 12, fontWeight: 700 }}>{asString(row.task_label) || `Task ${idx + 1}`}</div>
                    <div style={{ fontSize: 13, marginTop: 4 }}>
                      <MarkdownMathContent content={asString(row.result_text) || asString(row.result_latex)} />
                    </div>
                  </div>
                ))}
              </div>
            </details>
          </section>
        ) : null}

        {!isRefusal && state.quality ? (
          <section style={{ borderTop: "1px solid #e2e8f0", paddingTop: 12 }}>
            <details open={showQuality} onToggle={(e) => setShowQuality((e.target as HTMLDetailsElement).open)}>
              <summary style={{ cursor: "pointer", fontSize: 12, fontWeight: 700, color: "#334155" }}>Quality</summary>
              <div style={{ marginTop: 8, fontSize: 13 }}>
                {Array.isArray(state.quality.assumptions) && state.quality.assumptions.length > 0 ? (
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ fontWeight: 700, marginBottom: 4 }}>Assumptions</div>
                    <ul style={{ paddingInlineStart: 18 }}>
                      {state.quality.assumptions.map((entry, idx) => (
                        <li key={`assumption-${idx}`}>{asString(entry)}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {Array.isArray(state.quality.warnings) && state.quality.warnings.length > 0 ? (
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ fontWeight: 700, marginBottom: 4 }}>Warnings</div>
                    <ul style={{ paddingInlineStart: 18 }}>
                      {state.quality.warnings.map((entry, idx) => (
                        <li key={`warning-${idx}`}>{asString(entry)}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {typeof state.quality.confidence === "number" ? (
                  <div>Confidence: {Math.round(Number(state.quality.confidence) * 100)}%</div>
                ) : null}
              </div>
            </details>
          </section>
        ) : null}

        {contextEntries.length > 0 ? (
          <section style={{ borderTop: "1px solid #e2e8f0", paddingTop: 12 }}>
            <details open={showContext} onToggle={(e) => setShowContext((e.target as HTMLDetailsElement).open)}>
              <summary style={{ cursor: "pointer", fontSize: 12, fontWeight: 700, color: "#334155" }}>Context</summary>
              <div style={{ marginTop: 8, display: "grid", gap: 4, fontSize: 13 }}>
                {contextEntries.map(([key, value]) => (
                  <div key={`ctx-${key}`}>
                    <strong>{key.replaceAll("_", " ")}:</strong> {asString(value)}
                  </div>
                ))}
              </div>
            </details>
          </section>
        ) : null}

        {detailEntries.length > 0 ? (
          <section style={{ borderTop: "1px solid #e2e8f0", paddingTop: 12 }}>
            <details open={showDetails} onToggle={(e) => setShowDetails((e.target as HTMLDetailsElement).open)}>
              <summary style={{ cursor: "pointer", fontSize: 12, fontWeight: 700, color: "#334155" }}>Details</summary>
              <div style={{ marginTop: 8, display: "grid", gap: 4, fontSize: 13 }}>
                {detailEntries.map(([label, value]) => (
                  <div key={`detail-${label}`}>
                    <strong>{label}:</strong> {value}
                  </div>
                ))}
              </div>
            </details>
          </section>
        ) : null}

        <TypingIndicator visible={state.isTyping && !state.isComplete} />
      </div>
    </div>
  );
}
