"use client";

import React from "react";
import MathRenderer from "@/components/math/MathJaxRenderer";
import TypingPlaybackMessage from "./TypingPlaybackMessage";
import { NormalizedChatMessage, NormalizedContentItem } from "./types";
import styles from "./MathCanvas.module.css";

interface ChatMessageProps {
  message: NormalizedChatMessage;
  originalProblem?: string;
  direction?: "ltr" | "rtl";
  assistantContent?: string;
}

const normalizePromptPreview = (value: string): string => {
  return value
    .replace(/\\\(|\\\)|\\\[|\\\]/g, "")
    .replace(/\$/g, "")
    .replace(/\\text\{([^}]*)\}/g, "$1")
    .replace(/\\begin\{aligned\}/g, "")
    .replace(/\\end\{aligned\}/g, "")
    .replace(/\\begin\{[^}]+\}/g, "")
    .replace(/\\end\{[^}]+\}/g, "")
    .replace(/\\(?:newline|cr|quad|qquad|hfill)\b/g, " ")
    .replace(/\\\\/g, " ")
    .replace(/\r?\n/g, " ")
    .replace(/\\,/g, " ")
    .replace(/\\left|\\right/g, "")
    .replace(/\s+/g, " ")
    .trim();
};

const splitPromptPreview = (value: string): { lead: string; expr: string } => {
  const cleaned = normalizePromptPreview(value);
  const parts = cleaned.split(",");
  if (parts.length >= 2) {
    const lead = `${parts[0].trim()},`;
    const expr = parts.slice(1).join(",").trim();
    return { lead, expr };
  }
  return { lead: "", expr: cleaned };
};

const RenderAssistantItem = ({
  item,
  originalProblem,
}: {
  item: NormalizedContentItem;
  originalProblem?: string;
}) => {
  if (item.type === "text") {
    return (
      <div className={styles.chatBubbleAssistant}>
        <MathRenderer content={item.text} mode="prose" />
      </div>
    );
  }
  if (item.type === "math_solution") {
    // Prefer originalProblem > layoutTitle > recognizedLatex > "this problem"
    const contextContent = originalProblem || item.payload.layoutTitle || item.payload.recognizedLatex || "this problem";
    const { lead, expr } = splitPromptPreview(contextContent);

    return (
      <div className={styles.chatBubbleAssistant}>
        <div className={styles.chatPromptPreviewRow}>
          <span>Uask about anything related to {lead ? `${lead} ` : ""}</span>
          {expr ? (
            <span className={styles.inlineMathPreview}>
              <MathRenderer content={expr} mode="inline" />
            </span>
          ) : null}
        </div>
      </div>
    );
  }
  if (item.type === "chart") return null;
  return <div className={styles.chatBubbleAssistant}>{item.message}</div>;
};

export default function ChatMessage({ message, originalProblem, direction = "ltr", assistantContent }: ChatMessageProps) {
  const isRtl = direction === "rtl";
  if (message.role === "user") {
    const text = message.items.find((item) => item.type === "text");
    return (
      <div
        className={`${styles.chatBubbleRowUser} ${isRtl ? styles.chatBubbleRowUserRtl : ""}`.trim()}
        dir={direction}
      >
        <div className={`${styles.chatBubbleUser} ${isRtl ? styles.chatBubbleRtl : ""}`.trim()}>
          <MathRenderer content={text && text.type === "text" ? text.text : ""} mode="prose" />
        </div>
      </div>
    );
  }

  return (
    <div
      className={`${styles.chatBubbleRowAssistant} ${isRtl ? styles.chatBubbleRowAssistantRtl : ""}`.trim()}
      dir={direction}
    >
      <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-muted)", marginBottom: 4 }}>AI TUTOR</div>
      <div style={{ display: "grid", gap: 8, width: "100%" }}>
        {assistantContent && String(message.id || "").trim() ? (
          <TypingPlaybackMessage messageId={String(message.id)} fallbackContent={assistantContent} />
        ) : (
          message.items.map((item, index) => (
            <RenderAssistantItem key={`${message.id}-${index}`} item={item} originalProblem={originalProblem} />
          ))
        )}
      </div>
      <div className={`${styles.chatSolutionSignature} ${isRtl ? styles.chatSolutionSignatureRtl : ""}`.trim()}>Uask.ai</div>
    </div>
  );
}
