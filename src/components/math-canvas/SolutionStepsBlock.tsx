"use client";

import React from "react";
import MathRenderer from "@/components/math/MathRendererSwitch";
import { StepRow, VerificationCheck } from "./types";
import styles from "./MathCanvas.module.css";

interface SolutionStepsBlockProps {
  steps: StepRow[];
  result?: string;
  verificationChecks?: VerificationCheck[];
  sectionId?: string;
  editable?: boolean;
  onChange?: (next: { steps: StepRow[]; result?: string; verificationChecks?: VerificationCheck[] }) => void;
}

export default function SolutionStepsBlock({
  steps,
  result,
  verificationChecks,
  sectionId = "steps-block",
  editable = false,
  onChange,
}: SolutionStepsBlockProps) {
  const [editingStepIndex, setEditingStepIndex] = React.useState<number | null>(null);
  const [stepDraft, setStepDraft] = React.useState<StepRow>({ title: "", explanation: "", mathLatex: "" });
  const [editingResult, setEditingResult] = React.useState(false);
  const [resultDraft, setResultDraft] = React.useState(result || "");

  React.useEffect(() => {
    setResultDraft(result || "");
  }, [result]);

  const isGenericStepTitle = (title: string, index: number) => {
    const normalized = (title || "").trim().toLowerCase();
    if (!normalized) return true;
    if (normalized === `step ${index + 1}`) return true;
    return /^step\s+\d+$/.test(normalized);
  };

  const startEditStep = (index: number) => {
    setEditingStepIndex(index);
    setStepDraft({ ...steps[index] });
  };

  const saveStep = () => {
    if (editingStepIndex === null || !onChange) return;
    const nextSteps = steps.map((step, index) => (index === editingStepIndex ? { ...stepDraft } : step));
    onChange({ steps: nextSteps, result, verificationChecks });
    setEditingStepIndex(null);
  };

  const deleteStep = (index: number) => {
    if (!onChange) return;
    const nextSteps = steps.filter((_, stepIndex) => stepIndex !== index);
    onChange({ steps: nextSteps, result, verificationChecks });
    setEditingStepIndex(null);
  };

  return (
    <div className={styles.stepsBlock}>
      {steps.map((step, index) => (
        <div key={`${step.title}-${index}`} className={styles.stepRow} id={`${sectionId}-step-${index + 1}`}>
          <span className={styles.stepLabel}>STEP {index + 1}</span>
          <div className={styles.stepValue}>
            {editingStepIndex !== index ? (
              <span className={styles.stepTitleTag}>
                <strong>{!isGenericStepTitle(step.title, index) ? step.title : `Step ${index + 1}`}</strong>
              </span>
            ) : null}
            {editingStepIndex === index ? (
              <div className={styles.inlineEditWrap}>
                <input
                  className={styles.inlineEditInput}
                  value={stepDraft.title || ""}
                  placeholder={`Step ${index + 1} title`}
                  onChange={(event) => setStepDraft((prev) => ({ ...prev, title: event.target.value }))}
                />
                <textarea
                  className={styles.inlineEditTextArea}
                  value={stepDraft.explanation || ""}
                  placeholder="Step explanation"
                  onChange={(event) => setStepDraft((prev) => ({ ...prev, explanation: event.target.value }))}
                />
                <textarea
                  className={styles.inlineEditTextArea}
                  value={stepDraft.mathLatex || ""}
                  placeholder="LaTeX (optional)"
                  onChange={(event) => setStepDraft((prev) => ({ ...prev, mathLatex: event.target.value }))}
                />
                <div className={styles.blockActions}>
                  <button type="button" className={styles.blockActionButton} onClick={saveStep}>
                    Save
                  </button>
                  <button
                    type="button"
                    className={styles.blockActionButton}
                    onClick={() => setEditingStepIndex(null)}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <>
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
                {editable ? (
                  <div className={styles.blockActions}>
                    <button type="button" className={styles.blockActionButton} onClick={() => startEditStep(index)}>
                      Edit
                    </button>
                    <button type="button" className={styles.blockActionButton} onClick={() => deleteStep(index)}>
                      Delete
                    </button>
                  </div>
                ) : null}
              </>
            )}
          </div>
        </div>
      ))}
      <div className={styles.stepRow} id={`${sectionId}-final-answer`}>
        <span className={styles.stepLabel}>FINAL</span>
        <div className={styles.stepValue}>
          {editingResult ? (
            <div className={styles.inlineEditWrap}>
              <input
                className={styles.inlineEditInput}
                value={resultDraft}
                onChange={(event) => setResultDraft(event.target.value)}
              />
              <div className={styles.blockActions}>
                <button
                  type="button"
                  className={styles.blockActionButton}
                  onClick={() => {
                    onChange?.({ steps, result: resultDraft, verificationChecks });
                    setEditingResult(false);
                  }}
                >
                  Save
                </button>
                <button
                  type="button"
                  className={styles.blockActionButton}
                  onClick={() => {
                    setResultDraft(result || "");
                    setEditingResult(false);
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <>
              <span className={styles.resultBadge}>
                <strong>Final Answer:</strong>{" "}
                {result ? <MathRenderer content={result} mode="inline" /> : "Not provided."}
              </span>
              {editable ? (
                <div className={styles.blockActions}>
                  <button type="button" className={styles.blockActionButton} onClick={() => setEditingResult(true)}>
                    Edit
                  </button>
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>
      {Array.isArray(verificationChecks) && verificationChecks.length > 0 ? (
        <div className={styles.stepRow} id={`${sectionId}-verification`}>
          <span className={styles.stepLabel}>VERIFY</span>
          <div className={styles.stepValue}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>Verification:</div>
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
