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
}

const navItems = [
  { key: "overview", label: "Overview", icon: "home" },
  { key: "canvas", label: "Math Canvas", icon: "edit_note" },
];

export default function LeftNotebookSidebar({
  notebookTitle,
  notebookSubtitle,
  sessionId,
  outlineItems = [],
  classification,
  tokenUsage = { input_tokens: 0, output_tokens: 0, total_tokens: 0 },
  confidence,
}: LeftNotebookSidebarProps) {
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

      {typeof confidence === "number" && (
        <div style={{ padding: "0 16px 16px", marginBottom: 16, borderBottom: "1px solid #f1f5f9" }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase" }}>
            Confidence Score
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ flex: 1, height: 6, background: "#e2e8f0", borderRadius: 3, overflow: "hidden" }}>
              <div style={{ width: `${Math.min(100, Math.max(0, confidence * 100))}%`, height: "100%", background: confidence > 0.8 ? "#22c55e" : confidence > 0.5 ? "#f59e0b" : "#ef4444" }} />
            </div>
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-main)" }}>{Math.round(confidence * 100)}%</span>
          </div>
        </div>
      )}

      <nav className={styles.navList} aria-label="Notebook navigation">
        {navItems.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`${styles.navItem} ${item.key === "canvas" ? styles.navItemActive : ""}`}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
              {item.icon}
            </span>
            <span>{item.label}</span>
          </button>
        ))}
        {sessionId && (
          <a
            href={`/edit/${sessionId}`}
            className={styles.navItem}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
              edit
            </span>
            <span>Edit & Notes</span>
          </a>
        )}
      </nav>

      {outlineItems.length > 0 ? (
        <div className={styles.outlineWrap}>
          <div className={styles.outlineTitle}>Paper Outline</div>
          <div className={styles.outlineList}>
            {outlineItems.map((item) => (
              <a key={`${item.tag}-${item.id}`} href={`#${item.id}`} className={styles.outlineLink}>
                <span className={styles.outlineTag}>{item.tag}</span>
                <span>{item.label}</span>
              </a>
            ))}
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
