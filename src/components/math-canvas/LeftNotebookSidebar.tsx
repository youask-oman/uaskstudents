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
