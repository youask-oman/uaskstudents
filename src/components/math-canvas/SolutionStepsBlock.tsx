"use client";

import React from "react";
import MathRenderer from "@/components/math/MathRendererSwitch";
import { StepRow } from "./types";
import styles from "./MathCanvas.module.css";

interface SolutionStepsBlockProps {
  steps: StepRow[];
  result?: string;
}

export default function SolutionStepsBlock({ steps, result }: SolutionStepsBlockProps) {
  return (
    <div className={styles.stepsBlock}>
      {steps.map((step, index) => (
        <div key={`${step.title}-${index}`} className={styles.stepRow}>
          <span className={styles.stepLabel}>STEP {index + 1}</span>
          <div className={styles.stepValue}>
            <div style={{ fontWeight: 600 }}>{step.title}</div>
            {step.explanation ? <div style={{ marginTop: 3, fontSize: 13 }}>{step.explanation}</div> : null}
            {step.mathLatex ? (
              <div style={{ marginTop: 4 }}>
                <MathRenderer content={step.mathLatex} mode="inline" />
              </div>
            ) : null}
          </div>
        </div>
      ))}
      {result ? (
        <div className={styles.stepRow}>
          <span className={styles.stepLabel}>RESULT</span>
          <div className={styles.stepValue}>
            <span className={styles.resultBadge}>
              <MathRenderer content={result} mode="inline" />
            </span>
          </div>
        </div>
      ) : null}
    </div>
  );
}
