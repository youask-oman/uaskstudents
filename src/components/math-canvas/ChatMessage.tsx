"use client";

import React from "react";
import MathRenderer from "@/components/math/MathRendererSwitch";
import VisualRenderer from "@/components/workspace/VisualRenderer";
import { ChartPayload, NormalizedChatMessage, NormalizedContentItem } from "./types";
import styles from "./MathCanvas.module.css";

interface ChatMessageProps {
  message: NormalizedChatMessage;
  originalProblem?: string;
}

const toVisualSpec = (chart: ChartPayload): Record<string, unknown> => {
  const xValues = chart.points.map((point) => point.x);
  const yValues = chart.points.map((point) => point.y);
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues);
  const yMax = Math.max(...yValues);

  return {
    title: chart.title || "Graph",
    axes: {
      x_label: chart.xLabel || "x",
      y_label: chart.yLabel || "y",
      y_range: [yMin - 1, yMax + 1],
    },
    domain: {
      x_min_latex: String(xMin - 1),
      x_max_latex: String(xMax + 1),
    },
    series: [{ label: chart.title || "Series", points: chart.points }],
  };
};

const RenderAssistantItem = ({ item, originalProblem }: { item: NormalizedContentItem, originalProblem?: string }) => {
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

    return (
      <div className={styles.chatBubbleAssistant}>
        <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
          Uask about anything related to <MathRenderer content={contextContent} mode="inline" />
        </div>
      </div>
    );
  }
  if (item.type === "chart") {
    return (
      <div className={styles.chatBubbleAssistant}>
        <VisualRenderer visual={toVisualSpec(item.payload)} height={220} />
      </div>
    );
  }
  return <div className={styles.chatBubbleAssistant}>{item.message}</div>;
};

export default function ChatMessage({ message, originalProblem }: ChatMessageProps) {
  if (message.role === "user") {
    const text = message.items.find((item) => item.type === "text");
    return (
      <div className={styles.chatBubbleRowUser}>
        <div className={styles.chatBubbleUser}>
          <MathRenderer content={text && text.type === "text" ? text.text : ""} mode="prose" />
        </div>
      </div>
    );
  }

  return (
    <div className={styles.chatBubbleRowAssistant}>
      <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-muted)", marginBottom: 4 }}>AI TUTOR</div>
      <div style={{ display: "grid", gap: 8 }}>
        {message.items.map((item, index) => (
          <RenderAssistantItem key={`${message.id}-${index}`} item={item} originalProblem={originalProblem} />
        ))}
      </div>
      <div className={styles.chatSolutionSignature}>Uask.ai</div>
    </div>
  );
}
