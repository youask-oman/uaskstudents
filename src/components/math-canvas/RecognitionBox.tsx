"use client";

import React from "react";
import MathRenderer from "@/components/math/MathRendererSwitch";
import styles from "./MathCanvas.module.css";

interface RecognitionBoxProps {
  latex: string;
  exportMode?: boolean;
}

export default function RecognitionBox({ latex, exportMode = false }: RecognitionBoxProps) {
  return (
    <div className={styles.recognitionBox}>
      <MathRenderer content={latex} mode="prose" />
      {!exportMode ? (
        <div className={styles.recognizedBadge} data-no-export="true">
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>
            auto_fix_high
          </span>
          AI recognized
        </div>
      ) : null}
    </div>
  );
}
