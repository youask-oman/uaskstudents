"use client";

import React from "react";
import styles from "./MathCanvas.module.css";

interface TopHeaderProps {
  notebookTitle: string;
}

export default function TopHeader({ notebookTitle }: TopHeaderProps) {
  return (
    <header className={styles.topHeader}>
      <div className={styles.topHeaderLeft}>
        <div className={styles.logoBadge}>
          <span className="material-symbols-outlined">calculate</span>
        </div>
        <h1 className={styles.brandTitle}>Uask Canvas AI</h1>
        <div className={styles.searchWrap}>
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
            search
          </span>
          <input
            className={styles.searchInput}
            placeholder={`Search in ${notebookTitle}...`}
            aria-label="Search notes"
          />
        </div>
      </div>

      <div className={styles.topHeaderActions}>
        <button type="button" className={styles.headerButton}>
          Save
        </button>
        <button type="button" className={`${styles.headerButton} ${styles.headerButtonPrimary}`}>
          Export
        </button>
      </div>
    </header>
  );
}
