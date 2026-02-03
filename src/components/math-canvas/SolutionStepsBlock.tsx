"use client";

import React from "react";
import type { Editor } from "@tiptap/core";
import MathRenderer from "@/components/math/MathRendererSwitch";
import RichTextElementEditor from "./RichTextElementEditor";
import type { RichTextCommitPayload } from "./RichTextElementEditor";
import { StepRow, VerificationCheck } from "./types";
import styles from "./MathCanvas.module.css";

interface SolutionStepsBlockProps {
  steps: StepRow[];
  result?: string;
  verificationChecks?: VerificationCheck[];
  sectionId?: string;
  editable?: boolean;
  exportMode?: boolean;
  onActiveTextEditorChange?: (editor: Editor | null, elementId: string | null) => void;
  onChange?: (next: { steps: StepRow[]; result?: string; verificationChecks?: VerificationCheck[] }) => void;
}

const SAFE_PROTOCOL_RE = /^(https?:|mailto:)/i;

const sanitizeRichTextHtml = (html: string): string => {
  if (!html.trim()) return "";
  if (typeof window === "undefined") return html;
  const template = document.createElement("template");
  template.innerHTML = html;
  template.content.querySelectorAll("script, style, iframe, object, embed").forEach((node) => node.remove());
  template.content.querySelectorAll("*").forEach((node) => {
    [...node.attributes].forEach((attribute) => {
      const name = attribute.name.toLowerCase();
      if (name.startsWith("on")) node.removeAttribute(attribute.name);
    });
    if (node instanceof HTMLAnchorElement) {
      const href = node.getAttribute("href") || "";
      if (!SAFE_PROTOCOL_RE.test(href)) node.removeAttribute("href");
      node.setAttribute("target", "_blank");
      node.setAttribute("rel", "noopener noreferrer nofollow");
    }
  });
  return template.innerHTML;
};

const normalizedJson = (value: Record<string, unknown> | undefined): string => JSON.stringify(value || null);

const hasSameDraftContent = (draft: StepRow, payload: RichTextCommitPayload): boolean =>
  (draft.explanation || "") === payload.text &&
  (draft.explanationRichHtml || "") === (payload.richTextHtml || "") &&
  normalizedJson(draft.explanationRichJson) === normalizedJson(payload.richTextJson);

export default function SolutionStepsBlock({
  steps,
  result,
  verificationChecks,
  sectionId = "steps-block",
  editable = false,
  exportMode = false,
  onActiveTextEditorChange,
  onChange,
}: SolutionStepsBlockProps) {
  const [editingStepIndex, setEditingStepIndex] = React.useState<number | null>(null);
  const [stepDraft, setStepDraft] = React.useState<StepRow>({ title: "", explanation: "", mathLatex: "" });
  const [editingResult, setEditingResult] = React.useState(false);
  const [resultDraft, setResultDraft] = React.useState(result || "");
  const handleStepEditorActivate = React.useCallback(
    (editor: Editor | null, elementId: string | null) => onActiveTextEditorChange?.(editor, elementId),
    [onActiveTextEditorChange],
  );
  const handleStepEditorCommit = React.useCallback((payload: RichTextCommitPayload) => {
    setStepDraft((prev) => {
      if (hasSameDraftContent(prev, payload)) return prev;
      return {
        ...prev,
        explanation: payload.text,
        explanationRichHtml: payload.richTextHtml,
        explanationRichJson: payload.richTextJson,
      };
    });
  }, []);
  const handleStepEditorRequestClose = React.useCallback(() => {
    // Keep step edit form open; Save/Cancel controls handle form lifecycle.
  }, []);

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
        <div key={`${sectionId}-step-${index}`} className={styles.stepRow} id={`${sectionId}-step-${index + 1}`}>
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
                <div className={styles.inlineEditRichText}>
                  <RichTextElementEditor
                    key={`${sectionId}-step-editor-${index}`}
                    elementId={`${sectionId}-step-${index}`}
                    initialText={stepDraft.explanation || ""}
                    initialHtml={stepDraft.explanationRichHtml}
                    initialJson={stepDraft.explanationRichJson}
                    onActivate={handleStepEditorActivate}
                    onCommit={handleStepEditorCommit}
                    onRequestClose={handleStepEditorRequestClose}
                  />
                </div>
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
                {step.explanationRichHtml ? (
                  <div
                    style={{ marginTop: 3, fontSize: 13 }}
                    className={styles.richTextElementContent}
                    dangerouslySetInnerHTML={{ __html: sanitizeRichTextHtml(step.explanationRichHtml) }}
                  />
                ) : step.explanation ? (
                  <div style={{ marginTop: 3, fontSize: 13 }}>
                    <MathRenderer content={step.explanation} mode="prose" />
                  </div>
                ) : null}
                {step.mathLatex ? (
                  <div style={{ marginTop: 4 }}>
                    <MathRenderer content={step.mathLatex} mode="inline" />
                  </div>
                ) : null}
                {editable && !exportMode ? (
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
              {editable && !exportMode ? (
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
