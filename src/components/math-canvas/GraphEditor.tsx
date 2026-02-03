"use client";

import React, { useState } from "react";
import { parsePlotInput } from "./plotParser";
import { PlotDataPoint } from "./types";
import styles from "./MathCanvas.module.css";

interface GraphEditorProps {
  onClose: () => void;
  onInsert: (payload: {
    title: string;
    xLabel: string;
    yLabel: string;
    points: PlotDataPoint[];
  }) => void;
}

type TabType = "function" | "points";

export default function GraphEditor({ onClose, onInsert }: GraphEditorProps) {
  const [tab, setTab] = useState<TabType>("function");
  const [title, setTitle] = useState("Graph");
  const [xLabel, setXLabel] = useState("x");
  const [yLabel, setYLabel] = useState("y");
  const [functionInput, setFunctionInput] = useState("y = sin(x)");
  const [pointsInput, setPointsInput] = useState("(0,0)\n(1,1)\n(2,4)");
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    try {
      const parsedPoints =
        tab === "function"
          ? parsePlotInput({ mode: "function", expression: functionInput })
          : parsePlotInput({ mode: "points", pointsText: pointsInput });
      onInsert({
        title: title.trim() || "Graph",
        xLabel: xLabel.trim() || "x",
        yLabel: yLabel.trim() || "y",
        points: parsedPoints,
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not parse graph input.");
    }
  };

  return (
    <div className={styles.latexModalBackdrop} role="dialog" aria-modal="true" aria-label="Graph editor">
      <div className={styles.latexModal}>
        <div className={styles.modalHeaderRow}>
          <strong style={{ fontSize: 14 }}>Plot Graph</strong>
          <button type="button" className={styles.headerButton} onClick={onClose}>
            Close
          </button>
        </div>

        <div className={styles.graphTabRow}>
          <button
            type="button"
            className={`${styles.graphTabButton} ${tab === "function" ? styles.graphTabButtonActive : ""}`}
            onClick={() => setTab("function")}
          >
            Function
          </button>
          <button
            type="button"
            className={`${styles.graphTabButton} ${tab === "points" ? styles.graphTabButtonActive : ""}`}
            onClick={() => setTab("points")}
          >
            Points
          </button>
        </div>

        <div className={styles.graphMetaGrid}>
          <label className={styles.graphMetaField}>
            <span>Title</span>
            <input value={title} onChange={(event) => setTitle(event.target.value)} className={styles.composerInput} />
          </label>
          <label className={styles.graphMetaField}>
            <span>X Label</span>
            <input value={xLabel} onChange={(event) => setXLabel(event.target.value)} className={styles.composerInput} />
          </label>
          <label className={styles.graphMetaField}>
            <span>Y Label</span>
            <input value={yLabel} onChange={(event) => setYLabel(event.target.value)} className={styles.composerInput} />
          </label>
        </div>

        {tab === "function" ? (
          <textarea
            className={styles.latexInput}
            value={functionInput}
            onChange={(event) => setFunctionInput(event.target.value)}
            placeholder="y = 3x^2 + 2x"
            aria-label="Function input"
          />
        ) : (
          <textarea
            className={styles.latexInput}
            value={pointsInput}
            onChange={(event) => setPointsInput(event.target.value)}
            placeholder="(0,0)&#10;(1,1)&#10;(2,4)"
            aria-label="Points input"
          />
        )}

        {error ? <div className={styles.graphError}>{error}</div> : null}

        <div className={styles.latexActions}>
          <button type="button" className={styles.headerButton} onClick={onClose}>
            Cancel
          </button>
          <button type="button" className={`${styles.headerButton} ${styles.headerButtonPrimary}`} onClick={submit}>
            Insert Plot
          </button>
        </div>
      </div>
    </div>
  );
}
