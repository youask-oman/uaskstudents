"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import logo13 from "@/app/logo/logo-13.png";
import ChatMessage from "./ChatMessage";
import QuickActions from "./QuickActions";
import styles from "./MathCanvas.module.css";
import { NormalizedChatMessage, SessionMessage } from "./types";
import { buildSuggestionPrompts, normalizeAssistantMessage, sanitizePromptContext } from "./normalizer";

interface RightTutorChatProps {
  sessionId: string;
  initialMessages: NormalizedChatMessage[];
  originalProblem: string;
  stepTitles: string[];
  direction?: "ltr" | "rtl";
  classification?: {
    domain?: string;
    topic?: string;
  };
}

const quickActionSeed = ["Hint", "Solve", "Graph", "History"];

export default function RightTutorChat({
  sessionId,
  initialMessages,
  originalProblem,
  stepTitles,
  direction = "ltr",
  classification,
}: RightTutorChatProps) {
  const isRtl = direction === "rtl";
  const [messages, setMessages] = useState<NormalizedChatMessage[]>(initialMessages);
  const [loading, setLoading] = useState(false);
  const [input, setInput] = useState("");
  const [analysisPrompt, setAnalysisPrompt] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);
  const analysisLabel = useMemo(() => {
    if (!analysisPrompt) return "Analyzing...";
    const compact = analysisPrompt.replace(/\s+/g, " ").trim();
    const clipped = compact.length > 64 ? `${compact.slice(0, 61)}...` : compact;
    return `Analyzing ${clipped}`;
  }, [analysisPrompt]);

  useEffect(() => {
    setMessages(initialMessages);
  }, [initialMessages]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const actions = useMemo(() => {
    const generated = buildSuggestionPrompts(stepTitles);
    return Array.from(new Set([...quickActionSeed, ...generated])).slice(0, 4);
  }, [stepTitles]);

  const sendMessage = async (rawMessage: string) => {
    const message = rawMessage.trim();
    if (!message || loading) return;
    setAnalysisPrompt(message);

    const user: NormalizedChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      createdAt: new Date().toISOString(),
      items: [{ type: "text", text: message }],
    };
    setMessages((prev) => [...prev, user]);
    setInput("");
    setLoading(true);

    if (sessionId.startsWith("demo")) {
      const demoAssistant: SessionMessage = {
        role: "assistant",
        content: `Step 1: Identify the target.\nStep 2: Apply the rule.\nFinal Answer: ${message}`,
      };
      setMessages((prev) => [...prev, normalizeAssistantMessage(demoAssistant, prev.length + 1)]);
      setLoading(false);
      return;
    }

    try {
      const response = await fetch(`/api/v1/sessions/${sessionId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          context: {
            original_problem: sanitizePromptContext(originalProblem),
            classification,
            steps: stepTitles.map((title, index) => ({ index: index + 1, title })),
          },
        }),
      });

      if (!response.ok) {
        throw new Error("Chat request failed");
      }

      const data = (await response.json()) as Record<string, unknown>;
      const assistantRaw: SessionMessage = {
        role: "assistant",
        content:
          (typeof data.response === "string" && data.response) ||
          (typeof data.content === "string" && data.content) ||
          "I couldn't parse that request.",
        created_at: typeof data.created_at === "string" ? data.created_at : undefined,
        model_used: typeof data.model_used === "string" ? data.model_used : undefined,
      };
      setMessages((prev) => [...prev, normalizeAssistantMessage(assistantRaw, prev.length + 1)]);
    } catch (error) {
      const fallback: SessionMessage = {
        role: "assistant",
        content: `Error: ${error instanceof Error ? error.message : "Request failed"}`,
      };
      setMessages((prev) => [...prev, normalizeAssistantMessage(fallback, prev.length + 1)]);
    } finally {
      setLoading(false);
    }
  };

  const mapQuickActionToPrompt = (action: string): string => {
    switch (action) {
      case "Hint":
        return "Give me a concise hint for the current step.";
      case "Solve":
        return "Solve the full problem with concise steps.";
      case "Graph":
        return "Plot the graph and explain key points.";
      case "History":
        return "Summarize what we already solved so far.";
      default:
        return action;
    }
  };

  return (
    <aside className={styles.rightSidebar} dir={direction}>
      <div className={styles.chatHeader}>
        <div className={styles.chatHeaderTitle}>
          <div className={styles.chatHeaderIcon}>
            <Image src={logo13} alt="Uask Tutor" width={46} height={46} />
          </div>
          <div>
            <div>Uask Me</div>
            <span className={styles.chatHeaderStatus}>
              <span className={styles.chatHeaderStatusDot} />
              {analysisLabel}
            </span>
          </div>
        </div>
      </div>

      <div className={styles.chatScroll}>
        {messages.map((message) => (
          <ChatMessage
            key={message.id}
            message={message}
            originalProblem={originalProblem}
            direction={direction}
          />
        ))}
        {loading ? (
          <div className={`${styles.chatBubbleRowAssistant} ${isRtl ? styles.chatBubbleRowAssistantRtl : ""}`.trim()}>
            <div className={styles.tutorThinking}>
              <div className={styles.tutorThinkingDots} aria-hidden="true">
                <span />
                <span />
                <span />
              </div>
              <span>Tutor is thinking...</span>
            </div>
          </div>
        ) : null}
        <div ref={endRef} />
      </div>

      <div className={styles.chatComposer}>
        <QuickActions
          actions={actions}
          onSelect={(action) => {
            const prompt = mapQuickActionToPrompt(action);
            setInput(prompt);
          }}
        />
        <div className={styles.composerRow} style={{ marginTop: 10, flexDirection: isRtl ? "row-reverse" : "row" }}>
          <textarea
            className={styles.composerInput}
            dir={direction}
            style={{ textAlign: isRtl ? "right" : "left" }}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void sendMessage(input);
              }
            }}
            placeholder="Ask anything about the math..."
            rows={3}
          />
          <button
            type="button"
            className={styles.composerSend}
            onClick={() => void sendMessage(input)}
            disabled={loading || !input.trim()}
          >
            Send
          </button>
        </div>
      </div>
    </aside>
  );
}
