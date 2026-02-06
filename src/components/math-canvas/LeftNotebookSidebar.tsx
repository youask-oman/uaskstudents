"use client";

import React from "react";
import MathRenderer from "@/components/math/MathRendererSwitch";
import styles from "./MathCanvas.module.css";

interface LeftNotebookSidebarProps {
  notebookTitle: string;
  notebookSubtitle: string;
  usagePercent: number;
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
}

const navItems = [
  { key: "overview", label: "Overview", icon: "home" },
  { key: "canvas", label: "Math Canvas", icon: "edit_note" },
];

export default function LeftNotebookSidebar({
  notebookTitle,
  notebookSubtitle,
  usagePercent,
  outlineItems = [],
  classification,
}: LeftNotebookSidebarProps) {
  return (
    <aside className={styles.leftSidebar}>
      <p className={styles.sidebarLabel}>Notebook</p>
      <div className={styles.notebookCard}>
        <div className={styles.notebookTitle}>{notebookTitle}</div>
        <div className={styles.notebookMeta}>
          <MathRenderer content={notebookSubtitle} mode="inline" />
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

      <div className={styles.storageWrap}>
        <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Storage used</div>
        <div className={styles.storageTrack}>
          <div className={styles.storageValue} style={{ width: `${Math.max(0, Math.min(100, usagePercent))}%` }} />
        </div>
        <div style={{ marginTop: 6, fontSize: 11, color: "var(--text-muted)" }}>
          {usagePercent}% of quota
        </div>
      </div>
    </aside>
  );
}
