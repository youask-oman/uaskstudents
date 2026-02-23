"use client";

import { useEffect, useMemo, useState } from "react";
import CodeBlock from "@/components/code/CodeBlock";
import PlotCard from "@/components/plot/PlotCard";
import BlockRenderer from "@/components/solve/BlockRenderer";
import TypingIndicator from "@/components/solve/TypingIndicator";
import UnifiedMathRenderer from "@/components/math/UnifiedMathRenderer";
import MarkdownMathContent from "@/components/math/MarkdownMathContent";
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

  const finalText = useMemo(() => String(state.finalAnswer?.answer_text || ""), [state.finalAnswer]);
  const finalLatex = useMemo(() => String(state.finalAnswer?.answer_latex || ""), [state.finalAnswer]);

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

      {state.questionText ? (
        <section id={anchorPrefix ? `${anchorPrefix}-question` : undefined} style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, opacity: 0.7, marginBottom: 6 }}>QUESTION</div>
          <div>{state.questionText}</div>
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

      {finalText || finalLatex ? (
        <section id={anchorPrefix ? `${anchorPrefix}-final-answer` : undefined} style={{ border: "1px solid #bbf7d0", background: "#f0fdf4", borderRadius: 10, padding: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, opacity: 0.75, marginBottom: 6 }}>FINAL ANSWER</div>
          <div>
            {finalLatex ? (
              <UnifiedMathRenderer content={finalLatex} mode="block" />
            ) : (
              <MarkdownMathContent content={finalText} />
            )}
          </div>
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
