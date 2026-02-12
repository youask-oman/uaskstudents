"use client";

import React from "react";
import MathRenderer from "@/components/math/MathJaxRenderer";
import styles from "./MathCanvas.module.css";

interface RecognitionBoxProps {
  latex: string;
  exportMode?: boolean;
  badgeLabel?: string;
}

export default function RecognitionBox({ latex, exportMode = false, badgeLabel = "AI recognized" }: RecognitionBoxProps) {
  return (
    <div className={styles.recognitionBox}>
      <MathRenderer content={latex} mode="block" />
      {!exportMode ? (
        <div className={styles.recognizedBadge} data-no-export="true">
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>
            auto_fix_high
          </span>
          {badgeLabel}
        </div>
      ) : null}
    </div>
  );
}
