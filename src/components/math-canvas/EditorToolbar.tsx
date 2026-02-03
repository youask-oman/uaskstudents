"use client";

import React from "react";
import styles from "./MathCanvas.module.css";

interface EditorToolbarProps {
  onAddPage: () => void;
  onOpenLatexEditor: () => void;
}

const tools = [
  { icon: "title", title: "Text" },
  { icon: "functions", title: "LaTeX", accent: true, action: "latex" },
  { icon: "straighten", title: "Ruler" },
  { icon: "explore", title: "Compass", accent: true },
  { icon: "show_chart", title: "Chart" },
  { icon: "ink_eraser", title: "Eraser" },
  { icon: "palette", title: "Palette", accent: true },
];

export default function EditorToolbar({ onAddPage, onOpenLatexEditor }: EditorToolbarProps) {
  return (
    <div className={styles.toolbar}>
      <div className={styles.toolActions}>
        {tools.map((tool, index) => (
          <React.Fragment key={tool.icon}>
            {index === 2 || index === 5 ? <span className={styles.divider} /> : null}
            <button
              type="button"
              className={styles.toolButton}
              title={tool.title}
              onClick={tool.action === "latex" ? onOpenLatexEditor : undefined}
            >
              <span
                className={`material-symbols-outlined ${tool.accent ? styles.toolAccent : ""}`}
                style={{ fontSize: 20 }}
              >
                {tool.icon}
              </span>
            </button>
          </React.Fragment>
        ))}
      </div>
      <button type="button" className={styles.addPageButton} onClick={onAddPage}>
        <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
          add_circle
        </span>
        Add Page
      </button>
    </div>
  );
}
