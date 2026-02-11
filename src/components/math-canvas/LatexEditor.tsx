"use client";

import React, { useState } from "react";
import MathRenderer from "@/components/math/MathJaxRenderer";
import styles from "./MathCanvas.module.css";

interface LatexEditorProps {
  initialValue?: string;
  onClose: () => void;
  onInsert: (latex: string) => void;
}

export default function LatexEditor({ initialValue = "", onClose, onInsert }: LatexEditorProps) {
  const [value, setValue] = useState(initialValue);

  return (
    <div className={styles.latexModalBackdrop} role="dialog" aria-modal="true" aria-label="LaTeX editor">
      <div className={styles.latexModal}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
          <strong style={{ fontSize: 14 }}>Insert LaTeX</strong>
          <button type="button" className={styles.headerButton} onClick={onClose}>
            Close
          </button>
        </div>

        <textarea
          className={styles.latexInput}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder={"\\frac{d}{dx}(x^2) = 2x"}
        />

        <div style={{ marginTop: 10, border: "1px solid var(--border-color)", borderRadius: 10, padding: 10 }}>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6 }}>Preview</div>
          <MathRenderer content={value || "\\text{No equation yet}"} mode="inline" />
        </div>

        <div className={styles.latexActions}>
          <button type="button" className={styles.headerButton} onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className={`${styles.headerButton} ${styles.headerButtonPrimary}`}
            onClick={() => {
              const trimmed = value.trim();
              if (!trimmed) return;
              onInsert(trimmed);
              onClose();
            }}
          >
            Insert
          </button>
        </div>
      </div>
    </div>
  );
}
