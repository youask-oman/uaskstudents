"use client";

import React from "react";
import MathRenderer from "@/components/math/MathRendererSwitch";
import { StepRow, VerificationCheck } from "./types";
import styles from "./MathCanvas.module.css";

interface SolutionStepsBlockProps {
  steps: StepRow[];
  result?: string;
  verificationChecks?: VerificationCheck[];
}

export default function SolutionStepsBlock({ steps, result, verificationChecks }: SolutionStepsBlockProps) {
  return (
    <div className={styles.stepsBlock}>
      {steps.map((step, index) => (
        <div key={`${step.title}-${index}`} className={styles.stepRow}>
          <span className={styles.stepLabel}>STEP {index + 1}</span>
          <div className={styles.stepValue}>
            <div style={{ fontWeight: 600 }}>{step.title}</div>
            {step.explanation ? (
              <div style={{ marginTop: 3, fontSize: 13 }}>
                <MathRenderer content={step.explanation} mode="prose" />
              </div>
            ) : null}
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
      {Array.isArray(verificationChecks) && verificationChecks.length > 0 ? (
        <div className={styles.stepRow}>
          <span className={styles.stepLabel}>VERIFY</span>
          <div className={styles.stepValue}>
            {verificationChecks.map((check, index) => (
              <div key={`${check.checkId}-${index}`} style={{ marginBottom: index < verificationChecks.length - 1 ? 8 : 0 }}>
                <div style={{ fontWeight: 600 }}>{check.checkId} ({check.verdict.toUpperCase()})</div>
                <div style={{ fontSize: 13 }}>{check.message}</div>
                {check.evidenceMath ? (
                  <div style={{ marginTop: 3 }}>
                    <MathRenderer content={check.evidenceMath} mode="inline" />
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
