"use client";

import React from "react";
import styles from "./MathCanvas.module.css";

interface QuickActionsProps {
  actions: string[];
  onSelect: (action: string) => void;
}

export default function QuickActions({ actions, onSelect }: QuickActionsProps) {
  return (
    <div className={styles.quickActions}>
      {actions.map((action) => (
        <button
          key={action}
          type="button"
          className={styles.quickActionPill}
          onClick={() => onSelect(action)}
        >
          {action}
        </button>
      ))}
    </div>
  );
}
