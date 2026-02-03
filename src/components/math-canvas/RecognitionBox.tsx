"use client";

import React from "react";
import MathRenderer from "@/components/math/MathRendererSwitch";
import styles from "./MathCanvas.module.css";

interface RecognitionBoxProps {
  latex: string;
}

export default function RecognitionBox({ latex }: RecognitionBoxProps) {
  return (
    <div className={styles.recognitionBox}>
      <MathRenderer content={latex} mode="inline" />
      <div className={styles.recognizedBadge}>
        <span className="material-symbols-outlined" style={{ fontSize: 14 }}>
          auto_fix_high
        </span>
        AI recognized
      </div>
    </div>
  );
}
