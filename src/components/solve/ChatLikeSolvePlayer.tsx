"use client";

import { useEffect, useMemo, useState } from "react";
import CodeBlock from "@/components/code/CodeBlock";
import PlotCard from "@/components/plot/PlotCard";
import BlockRenderer from "@/components/solve/BlockRenderer";
import TypingIndicator from "@/components/solve/TypingIndicator";
import UnifiedMathRenderer from "@/components/math/UnifiedMathRenderer";
import { useRenderPlayback, type RenderEvent } from "@/lib/playback/useRenderPlayback";

interface Props {
  messageId: string;
  fallbackContent: string;
  anchorPrefix?: string;
}

const fallbackEvents = (text: string): RenderEvent[] => [
  { id: "evt_00001", at_ms: 0, type: "MESSAGE_START", payload: {} },
  { id: "evt_00002", at_ms: 10, type: "QUESTION_SET", payload: { item_index: 1, question_id: "q1", text: "Solution" } },
  { id: "evt_00003", at_ms: 20, type: "STEP_START", payload: { item_index: 1, question_id: "q1", step_index: 1, title: "Solution" } },
  { id: "evt_00004", at_ms: 30, type: "BLOCK_APPEND_TEXT", payload: { item_index: 1, question_id: "q1", step_index: 1, block_id: "q1_s1_b1", chunk: text } },
  { id: "evt_00005", at_ms: 50, type: "STEP_END", payload: { item_index: 1, question_id: "q1", step_index: 1 } },
  { id: "evt_00006", at_ms: 60, type: "MESSAGE_END", payload: {} },
];

const decodeEscapedMathText = (value: unknown): string => {
  let text = typeof value === "string" ? value : value == null ? "" : String(value);
  if (!text) return "";
  // Recover a common corruption where "\text" became TAB + "ext".
  text = text.replace(/\text(?=[({])/g, "\\text");
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
    .replace(/\\\\([a-zA-Z]+)/g, "\\$1");
  return text;
};

const looksMathy = (value: string): boolean => {
  const text = String(value || "").trim();
  if (!text) return false;
  if (/[√∫∑πθ∞≤≥≈]/.test(text)) return true;
  if (/\\[a-zA-Z]+/.test(text)) return true;
  if (/[=^_]/.test(text)) return true;
  return false;
};

function normalizeQuestionForDisplay(raw: string): string {
  let text = decodeEscapedMathText(raw);
  if (!text) return "";
  text = text
    .replace(/\?_\{n=1\}\^\{\?\}/g, "\\sum_{n=1}^{\\infty}")
    .replace(/\?unknown exact closed form\?/gi, '"unknown exact closed form"')
    .replace(/\s\*\s/g, " ");
  // Wrap common plain-TeX fragments so MarkdownMathContent renders SVG math.
  text = text.replace(/(\(-1\)\^\{n\+1\}\/n\^2)/g, "\\($1\\)");
  text = text.replace(/(\\sum_\{[^}]+\}\^\{[^}]+\})/g, "\\($1\\)");
  return text;
}

export default function ChatLikeSolvePlayer({ messageId, fallbackContent, anchorPrefix }: Props) {
  const [events, setEvents] = useState<RenderEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [instant, setInstant] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/v1/chat_final/playback_state?message_id=${encodeURIComponent(messageId)}`, { cache: "no-store" });
        if (!res.ok) throw new Error("playback_state_unavailable");
        const body = await res.json();
        const remoteEvents = Array.isArray(body?.render_events) ? body.render_events : [];
        if (cancelled) return;
        if (remoteEvents.length > 0) {
          setEvents(remoteEvents as RenderEvent[]);
        } else {
          setEvents(fallbackEvents(fallbackContent));
        }
      } catch {
        if (!cancelled) setEvents(fallbackEvents(fallbackContent));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [fallbackContent, messageId]);

  const { state, replay, skipToEnd } = useRenderPlayback(events);

  useEffect(() => {
    if (instant) skipToEnd();
  }, [instant, skipToEnd]);

  const questionText = useMemo(() => normalizeQuestionForDisplay(String(state.questionText || "")), [state.questionText]);
  const finalText = useMemo(() => decodeEscapedMathText(state.finalAnswer?.answer_text || ""), [state.finalAnswer]);
  const finalLatex = useMemo(() => decodeEscapedMathText(state.finalAnswer?.answer_latex || ""), [state.finalAnswer]);
  const finalValues = useMemo(() => {
    const raw = state.finalAnswer?.values;
    return Array.isArray(raw) ? raw : [];
  }, [state.finalAnswer]);

  const plotPayload = state.plot || null;
  const plotAttemptId = typeof state.plot?.attempt_id === "string" ? String(state.plot.attempt_id) : undefined;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <label style={{ fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
          <input type="checkbox" checked={instant} onChange={(e) => setInstant(e.target.checked)} />
          Show instantly
        </label>
        <button type="button" onClick={replay} style={{ border: "1px solid #cbd5e1", borderRadius: 6, padding: "2px 8px", fontSize: 12 }}>
          Replay
        </button>
      </div>

      {questionText ? (
        <section id={anchorPrefix ? `${anchorPrefix}-question` : undefined} style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, opacity: 0.7, marginBottom: 6 }}>QUESTION</div>
          <UnifiedMathRenderer content={questionText} mode="prose" />
        </section>
      ) : null}

      {state.steps.map((step) => (
        <section
          key={`step-${step.stepIndex}`}
          id={anchorPrefix ? `${anchorPrefix}-playback-step-${step.stepIndex}` : undefined}
          style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 10 }}
        >
          <div style={{ fontSize: 11, fontWeight: 700, opacity: 0.75, marginBottom: 6 }}>{step.title}</div>
          <div>
            {step.blocks.map((block) => (
              <BlockRenderer key={block.id} block={block} />
            ))}
          </div>
        </section>
      ))}

      {finalText || finalLatex || finalValues.length > 0 ? (
        <section id={anchorPrefix ? `${anchorPrefix}-final-answer` : undefined} style={{ border: "1px solid #bbf7d0", background: "#f0fdf4", borderRadius: 10, padding: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, opacity: 0.75, marginBottom: 6 }}>FINAL ANSWER</div>
          {finalText ? <UnifiedMathRenderer content={finalText} mode={looksMathy(finalText) ? "prose" : "prose"} /> : null}
          {finalLatex ? <UnifiedMathRenderer content={finalLatex} mode="block" /> : null}
          {finalValues.length > 0 ? (
            <div style={{ marginTop: 10, overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", borderBottom: "1px solid #86efac", padding: "6px 8px" }}>Label</th>
                    <th style={{ textAlign: "left", borderBottom: "1px solid #86efac", padding: "6px 8px" }}>Value</th>
                    <th style={{ textAlign: "left", borderBottom: "1px solid #86efac", padding: "6px 8px" }}>LaTeX</th>
                  </tr>
                </thead>
                <tbody>
                  {finalValues.map((entry, idx) => {
                    const row = entry && typeof entry === "object" ? (entry as Record<string, unknown>) : {};
                    const label = decodeEscapedMathText(row.label ?? row.key ?? "");
                    const valueRaw = row.value ?? row.text ?? row.number ?? "";
                    const valueText = decodeEscapedMathText(typeof valueRaw === "string" ? valueRaw : String(valueRaw ?? ""));
                    const valueLatex = decodeEscapedMathText(row.value_latex ?? row.latex ?? "");
                    return (
                      <tr key={`final-value-${idx}`}>
                        <td style={{ borderBottom: "1px solid #dcfce7", padding: "6px 8px", verticalAlign: "top" }}>
                          {label ? (
                            looksMathy(label) ? <UnifiedMathRenderer content={label} mode="inline" /> : <span>{label}</span>
                          ) : "-"}
                        </td>
                        <td style={{ borderBottom: "1px solid #dcfce7", padding: "6px 8px", verticalAlign: "top" }}>
                          {valueText ? (
                            looksMathy(valueText) ? <UnifiedMathRenderer content={valueText} mode="inline" /> : <span>{valueText}</span>
                          ) : "-"}
                        </td>
                        <td style={{ borderBottom: "1px solid #dcfce7", padding: "6px 8px", verticalAlign: "top" }}>
                          {valueLatex ? (
                            looksMathy(valueLatex) ? <UnifiedMathRenderer content={valueLatex} mode="inline" /> : <span>{valueLatex}</span>
                          ) : "-"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      ) : null}

      {plotPayload ? (
        <section style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, opacity: 0.75, marginBottom: 6 }}>PLOT</div>
          <PlotCard plot={plotPayload} attemptId={plotAttemptId} playbackVisible={true} />
        </section>
      ) : null}

      {state.pythonCode ? (
        <section style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, opacity: 0.75, marginBottom: 6 }}>PYTHON</div>
          <CodeBlock code={state.pythonCode} language="python" />
        </section>
      ) : null}

      <TypingIndicator visible={!loading && state.isTyping} />
    </div>
  );
}
