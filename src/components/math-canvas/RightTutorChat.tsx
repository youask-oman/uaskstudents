"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import logo10 from "@/app/logo/logo-10.png";
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
  classification?: {
    domain?: string;
    topic?: string;
  };
}

const quickActionSeed = ["Simplify Eq", "Plot Graph", "Check Steps"];

export default function RightTutorChat({
  sessionId,
  initialMessages,
  originalProblem,
  stepTitles,
  classification,
}: RightTutorChatProps) {
  const [messages, setMessages] = useState<NormalizedChatMessage[]>(initialMessages);
  const [loading, setLoading] = useState(false);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setMessages(initialMessages);
  }, [initialMessages]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const actions = useMemo(() => {
    const generated = buildSuggestionPrompts(stepTitles);
    return Array.from(new Set([...quickActionSeed, ...generated])).slice(0, 5);
  }, [stepTitles]);

  const sendMessage = async (rawMessage: string) => {
    const message = rawMessage.trim();
    if (!message || loading) return;

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
      case "Simplify Eq":
        return "Simplify this equation and show concise steps.";
      case "Plot Graph":
        return "Plot the graph and explain key points.";
      case "Check Steps":
        return "Check each step for mistakes.";
      default:
        return action;
    }
  };

  return (
    <aside className={styles.rightSidebar}>
      <div className={styles.chatHeader}>
        <div className={styles.chatHeaderTitle}>
          <Image src={logo10} alt="Uask.ai" width={26} height={26} className={styles.chatTutorLogo} />
          Uask AI Tutor
        </div>
      </div>

      <div className={styles.chatScroll}>
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}
        {loading ? (
          <div className={styles.chatBubbleRowAssistant}>
            <div className={styles.chatBubbleAssistant}>Thinking...</div>
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
        <div className={styles.composerRow} style={{ marginTop: 10 }}>
          <input
            className={styles.composerInput}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void sendMessage(input);
              }
            }}
            placeholder="Ask anything about the math..."
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
