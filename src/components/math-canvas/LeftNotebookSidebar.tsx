"use client";

import React from "react";
import MathRenderer from "@/components/math/MathRendererSwitch";
import styles from "./MathCanvas.module.css";

interface LeftNotebookSidebarProps {
  notebookTitle: string;
  notebookSubtitle: string;
  usagePercent: number;
}

const navItems = [
  { key: "overview", label: "Overview", icon: "home" },
  { key: "canvas", label: "Math Canvas", icon: "edit_note" },
  { key: "geometry", label: "Geometry Tools", icon: "category" },
  { key: "stats", label: "Statistics", icon: "analytics" },
  { key: "history", label: "Revision History", icon: "history" },
];

export default function LeftNotebookSidebar({
  notebookTitle,
  notebookSubtitle,
  usagePercent,
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
