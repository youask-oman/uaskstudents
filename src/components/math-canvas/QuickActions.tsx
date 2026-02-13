"use client";

import React from "react";
import styles from "./MathCanvas.module.css";

interface QuickActionsProps {
  actions: string[];
  onSelect: (action: string) => void;
}

const actionIconByLabel: Record<string, string> = {
  Hint: "lightbulb",
  Solve: "calculate",
  Graph: "auto_graph",
  History: "history_edu",
};

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
          <span className="material-symbols-outlined" aria-hidden="true">
            {actionIconByLabel[action] || "bolt"}
          </span>
          {action}
        </button>
      ))}
    </div>
  );
}
