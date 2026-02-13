"use client";

import React from "react";
import MathRenderer from "@/components/math/MathJaxRenderer";
import styles from "./MathCanvas.module.css";

interface LeftNotebookSidebarProps {
  notebookTitle: string;
  notebookSubtitle: string;
  sessionId?: string;
  outlineItems?: Array<{
    id: string;
    label: string;
    tag: string;
  }>;
  classification?: {
    domain?: string;
    topic?: string;
    grade_band?: string;
    difficulty?: string;
  };
  tokenUsage?: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };
  confidence?: number;
  onOutlineSelect?: (id: string) => void;
}

export default function LeftNotebookSidebar({
  notebookTitle,
  notebookSubtitle,
  outlineItems = [],
  classification,
  tokenUsage = { input_tokens: 0, output_tokens: 0, total_tokens: 0 },
  confidence,
  onOutlineSelect,
}: LeftNotebookSidebarProps) {
  const clampedConfidence = typeof confidence === "number" ? Math.max(0, Math.min(1, confidence)) : null;
  const confidencePercent = clampedConfidence === null ? null : Math.round(clampedConfidence * 100);
  const ringCircumference = 2 * Math.PI * 34;
  const ringOffset = confidencePercent === null ? ringCircumference : ringCircumference * (1 - confidencePercent / 100);

  return (
    <aside className={styles.leftSidebar}>
      <p className={styles.sidebarLabel}>Notebook</p>
      <div className={styles.notebookCard}>
        <div className={styles.notebookTitle}>{notebookTitle}</div>
        <div className={styles.notebookMeta}>
          <MathRenderer content={notebookSubtitle} mode="prose" />
        </div>
      </div>

      {classification && (
        <div style={{ padding: "0 10px 18px", display: "flex", flexWrap: "wrap", gap: "6px" }}>
          {classification.domain && (
            <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 12, background: "#e0f2fe", color: "#0369a1", fontWeight: 600, border: "1px solid #bae6fd" }}>
              {classification.domain}
            </span>
          )}
          {classification.grade_band && (
            <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 12, background: "#f3e8ff", color: "#7e22ce", fontWeight: 600, border: "1px solid #e9d5ff" }}>
              {classification.grade_band}
            </span>
          )}
          {classification.topic && (
            <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 12, background: "#f1f5f9", color: "#475569", fontWeight: 600, border: "1px solid #e2e8f0" }}>
              {classification.topic}
            </span>
          )}
          {classification.difficulty && (
            <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 12, background: "#f0fdf4", color: "#15803d", fontWeight: 600, border: "1px solid #bbf7d0", textTransform: "capitalize" }}>
              {classification.difficulty}
            </span>
          )}
        </div>
      )}

      {outlineItems.length > 0 ? (
        <div className={styles.outlineWrap}>
          <div className={styles.outlineTitle}>Paper Outline</div>
          <div className={styles.outlineListStudio}>
            <div className={styles.outlineProgressRail} aria-hidden="true" />
            {outlineItems.map((item, index) => (
              <button
                key={`${item.tag}-${item.id}`}
                type="button"
                className={styles.outlineNodeButton}
                onClick={() => {
                  onOutlineSelect?.(item.id);
                  if (!onOutlineSelect && typeof document !== "undefined") {
                    document.getElementById(item.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
                  }
                }}
              >
                <span className={`${styles.outlineDot} ${index < 2 ? styles.outlineDotDone : ""}`} aria-hidden="true" />
                <span className={styles.outlineContent}>
                  <span className={styles.outlineTag}>{item.tag}</span>
                  <span>{item.label}</span>
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {confidencePercent !== null ? (
        <div className={styles.confidenceCard}>
          <div className={styles.confidenceHead}>
            <span className={styles.outlineTitle}>Confidence</span>
            <span className={styles.confidenceValue}>{confidencePercent}%</span>
          </div>
          <div className={styles.confidenceRingWrap}>
            <svg className={styles.confidenceRing} viewBox="0 0 84 84" aria-hidden="true">
              <circle cx="42" cy="42" r="34" className={styles.confidenceTrack} />
              <circle
                cx="42"
                cy="42"
                r="34"
                className={styles.confidenceBar}
                strokeDasharray={ringCircumference}
                strokeDashoffset={ringOffset}
              />
            </svg>
            <span className="material-symbols-outlined">school</span>
          </div>
        </div>
      ) : null}

      <div className={styles.storageWrap} style={{ padding: "16px", background: "rgba(248, 250, 252, 0.5)", borderRadius: "12px", border: "1px dashed #e2e8f0" }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-main)", marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
          <span className="material-symbols-outlined" style={{ fontSize: 14, color: "var(--primary-color)" }}>verified</span>
          Provider: <span style={{ color: "var(--primary-color)" }}>Uask AI</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "4px", fontSize: 10, color: "var(--text-muted)" }}>
          <span>Input Tokens</span>
          <span style={{ fontWeight: 600 }}>{tokenUsage.input_tokens.toLocaleString()}</span>
          <span>Output Tokens</span>
          <span style={{ fontWeight: 600 }}>{tokenUsage.output_tokens.toLocaleString()}</span>
          <div style={{ gridColumn: "span 2", height: "1px", background: "#e2e8f0", margin: "4px 0" }} />
          <span style={{ fontWeight: 700, color: "var(--text-main)" }}>Total Tokens</span>
          <span style={{ fontWeight: 700, color: "var(--text-main)" }}>{tokenUsage.total_tokens.toLocaleString()}</span>
        </div>
      </div>
    </aside>
  );
}
