"use client";

import React from "react";
import MathRenderer from "@/components/math/MathJaxRenderer";
import styles from "./MathCanvas.module.css";

interface RecognitionBoxProps {
  latex: string;
  exportMode?: boolean;
  badgeLabel?: string;
  plainStyle?: boolean;
  finalHandwritten?: boolean;
}

const hasStandaloneMathDelimiters = (text: string): boolean => {
  const trimmed = (text || "").trim();
  if (!trimmed) return false;
  if ((trimmed.startsWith("\\(") && trimmed.endsWith("\\)")) || (trimmed.startsWith("\\[") && trimmed.endsWith("\\]"))) {
    return true;
  }
  if ((trimmed.startsWith("$$") && trimmed.endsWith("$$")) || (trimmed.startsWith("$") && trimmed.endsWith("$"))) {
    return true;
  }
  return false;
};

const shouldRenderAsProse = (value: string): boolean => {
  const text = (value || "").trim();
  if (!text) return false;
  if (hasStandaloneMathDelimiters(text)) return false;
  if (/^\\begin\{(?:aligned|align|gather|equation|cases|pmatrix|bmatrix|matrix)\}/.test(text)) return false;

  const hasMathCommand = /\\[a-zA-Z]+/.test(text);
  const hasMathOperators = /[=^_<>+\-*/]/.test(text);
  const hasBraces = /[{}]/.test(text);
  const plainWordCount = (text.match(/(?<!\\)\b[A-Za-z]{3,}\b/g) || []).length;

  // Pure prose (no math signals) should always render as prose.
  if (!hasMathCommand && !hasMathOperators && !hasBraces) return true;

  // Command-heavy LaTeX with no natural-language words should remain math.
  if (hasMathCommand && plainWordCount === 0) return false;

  // Mixed prose + math should render as prose to preserve spacing.
  if (plainWordCount >= 3) return true;

  // Short equation-like snippets should remain math.
  return false;
};

export default function RecognitionBox({
  latex,
  exportMode = false,
  badgeLabel = "AI recognized",
  plainStyle = false,
  finalHandwritten = false,
}: RecognitionBoxProps) {
  if (finalHandwritten) {
    return (
      <div className={styles.recognitionBoxFinalHandwritten}>
        <div className={styles.recognitionMetaFinalHandwritten}>{String(badgeLabel || "PROBLEM").toUpperCase()}</div>
        <div className={styles.recognitionContentFinalHandwritten}>
          <MathRenderer content={latex} mode="prose" />
        </div>
      </div>
    );
  }

  return (
    <div className={`${styles.recognitionBox} ${plainStyle ? styles.recognitionBoxPlain : ""}`.trim()}>
      <MathRenderer content={latex} mode="prose" />
      {!exportMode ? (
        <div className={styles.recognizedBadge} data-no-export="true">
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>
            auto_fix_high
          </span>
          {badgeLabel}
        </div>
      ) : null}
    </div>
  );
}
