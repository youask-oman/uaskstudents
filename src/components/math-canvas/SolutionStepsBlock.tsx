"use client";

import React from "react";
import type { Editor } from "@tiptap/core";
import MathRenderer from "@/components/math/MathJaxRenderer";
import RichTextElementEditor from "./RichTextElementEditor";
import type { RichTextCommitPayload } from "./RichTextElementEditor";
import { StepRow, VerificationCheck, FinalAnswer } from "./types";
import { parseLatexToBlocks } from "@/lib/final-answer-layout-engine";
import { useMathOverflowFix } from "@/hooks/useMathOverflowFix";
import styles from "./MathCanvas.module.css";

interface SolutionStepsBlockProps {
  steps: StepRow[];
  result?: string;
  finalAnswer?: FinalAnswer;
  verificationChecks?: VerificationCheck[];
  domainConstraints?: string[];
  assumptions?: string[];
  originalProblem?: string;
  normalizedProblem?: string;
  commonMistakes?: string[];
  autocorrectApplied?: boolean;
  sectionId?: string;
  editable?: boolean;
  exportMode?: boolean;
  onActiveTextEditorChange?: (editor: Editor | null, elementId: string | null) => void;
  onChange?: (next: {
    steps: StepRow[];
    result?: string;
    verificationChecks?: VerificationCheck[];
    finalAnswer?: FinalAnswer;
    assumptions?: string[];
    originalProblem?: string;
    normalizedProblem?: string;
  }) => void;
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

/* Section row component for consistent alignment */
const SectionRow: React.FC<{ label: string; id: string; style?: React.CSSProperties; children: React.ReactNode }> = ({ label, id, style, children }) => (
  <div className={styles.stepRow} id={id} style={style}>
    <span className={styles.stepLabel}>{label}</span>
    <div className={styles.stepValue}>{children}</div>
  </div>
);

export default function SolutionStepsBlock({
  steps,
  result,
  finalAnswer,
  verificationChecks,
  domainConstraints,
  assumptions,
  originalProblem,
  normalizedProblem,
  commonMistakes,
  autocorrectApplied,
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

  // Editing states for new sections
  const [editingProblem, setEditingProblem] = React.useState(false);
  const [problemDraft, setProblemDraft] = React.useState({ original: originalProblem || "", normalized: normalizedProblem || "" });
  const [editingAssumptions, setEditingAssumptions] = React.useState(false);
  const [assumptionsDraft, setAssumptionsDraft] = React.useState<string[]>(assumptions || []);

  const handleStepEditorActivate = React.useCallback(
    (editor: Editor | null, elementId: string | null) => onActiveTextEditorChange?.(editor, elementId),
    [onActiveTextEditorChange],
  );

  const rootRef = React.useRef<HTMLDivElement>(null);
  useMathOverflowFix(rootRef);

  const handleStepTitleCommit = React.useCallback((payload: RichTextCommitPayload) => {
    setStepDraft((prev) => ({
      ...prev,
      title: payload.text,
      titleRichHtml: payload.richTextHtml,
      titleRichJson: payload.richTextJson,
    }));
  }, []);

  const handleStepExplanationCommit = React.useCallback((payload: RichTextCommitPayload) => {
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

  const handleStepMathCommit = React.useCallback((payload: RichTextCommitPayload) => {
    setStepDraft((prev) => ({
      ...prev,
      mathLatex: payload.text,
      mathRichHtml: payload.richTextHtml,
      mathRichJson: payload.richTextJson,
    }));
  }, []);

  const handleStepEditorRequestClose = React.useCallback(() => { }, []);

  React.useEffect(() => {
    setResultDraft(result || "");
  }, [result]);

  React.useEffect(() => {
    setProblemDraft({ original: originalProblem || "", normalized: normalizedProblem || "" });
  }, [originalProblem, normalizedProblem]);

  React.useEffect(() => {
    setAssumptionsDraft(assumptions || []);
  }, [assumptions]);

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
    onChange({
      steps: nextSteps,
      result,
      verificationChecks,
      finalAnswer,
      assumptions,
      originalProblem,
      normalizedProblem,
    });
    setEditingStepIndex(null);
  };

  const deleteStep = (index: number) => {
    if (!onChange) return;
    const nextSteps = steps.filter((_, stepIndex) => stepIndex !== index);
    onChange({
      steps: nextSteps,
      result,
      verificationChecks,
      finalAnswer,
      assumptions,
      originalProblem,
      normalizedProblem,
    });
    setEditingStepIndex(null);
  };

  // Compute display values for final answer
  const displayAnswerText = finalAnswer?.answer_text || "";
  const displayAnswerLatex = finalAnswer?.answer_latex || result || "";
  const displayValues = finalAnswer?.values || [];

  return (
    <div className={styles.stepsBlock} ref={rootRef}>
      {/* Domain Constraints */}
      {Array.isArray(domainConstraints) && domainConstraints.length > 0 && (
        <SectionRow label="DOMAIN" id={`${sectionId}-domain`}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Domain constraints:</div>
          {domainConstraints.map((constraint, index) => (
            <div key={`${sectionId}-domain-${index}`} style={{ marginBottom: index < domainConstraints.length - 1 ? 6 : 0 }}>
              <MathRenderer content={constraint} mode="prose" />
            </div>
          ))}
        </SectionRow>
      )}

      {/* Problem Statement Section */}
      {(originalProblem || normalizedProblem) && (
        <SectionRow label="PROBLEM" id={`${sectionId}-problem`}>
          {editingProblem ? (
            <div className={styles.inlineEditWrap}>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase" }}>Original Problem</div>
                <textarea
                  className={styles.inlineEditTextArea}
                  style={{ minHeight: 80, width: "100%", whiteSpace: "pre-wrap" }}
                  value={problemDraft.original}
                  onChange={(e) => setProblemDraft((prev) => ({ ...prev, original: e.target.value }))}
                />
              </div>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase" }}>Normalized Interpretation</div>
                <textarea
                  className={styles.inlineEditTextArea}
                  style={{ minHeight: 60, width: "100%", whiteSpace: "pre-wrap" }}
                  value={problemDraft.normalized}
                  onChange={(e) => setProblemDraft((prev) => ({ ...prev, normalized: e.target.value }))}
                />
              </div>
              <div className={styles.blockActions}>
                <button
                  type="button"
                  className={styles.blockActionButton}
                  onClick={() => {
                    onChange?.({
                      steps,
                      result,
                      verificationChecks,
                      finalAnswer,
                      assumptions,
                      originalProblem: problemDraft.original,
                      normalizedProblem: problemDraft.normalized,
                    });
                    setEditingProblem(false);
                  }}
                >
                  Save
                </button>
                <button type="button" className={styles.blockActionButton} onClick={() => { setProblemDraft({ original: originalProblem || "", normalized: normalizedProblem || "" }); setEditingProblem(false); }}>Cancel</button>
              </div>
            </div>
          ) : (
            <>
              {originalProblem && (
                <div style={{ marginBottom: normalizedProblem ? 12 : 0 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase" }}>Original Problem</div>
                  <div style={{ whiteSpace: "pre-wrap", fontSize: 13, color: "var(--text-main)", lineHeight: 1.6 }}>{originalProblem}</div>
                </div>
              )}
              {normalizedProblem && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase" }}>Normalized Interpretation</div>
                  <div style={{ whiteSpace: "pre-wrap", fontSize: 13, color: "var(--text-main)", lineHeight: 1.6 }}><MathRenderer content={normalizedProblem} mode="prose" /></div>
                </div>
              )}
              {editable && !exportMode && (
                <div className={styles.blockActions} style={{ marginTop: 8 }}>
                  <button type="button" className={styles.blockActionButton} onClick={() => setEditingProblem(true)}>Edit</button>
                </div>
              )}
            </>
          )}
        </SectionRow>
      )}

      {/* Assumptions Section */}
      {Array.isArray(assumptions) && assumptions.length > 0 && (
        <SectionRow label="ASSUMPTIONS" id={`${sectionId}-assumptions`}>
          {editingAssumptions ? (
            <div className={styles.inlineEditWrap}>
              {assumptionsDraft.map((assumption, index) => (
                <div key={index} style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                  <input
                    className={styles.inlineEditInput}
                    style={{ flex: 1 }}
                    value={assumption}
                    onChange={(e) => {
                      const next = [...assumptionsDraft];
                      next[index] = e.target.value;
                      setAssumptionsDraft(next);
                    }}
                  />
                  <button type="button" className={styles.blockActionButton} onClick={() => setAssumptionsDraft(assumptionsDraft.filter((_, i) => i !== index))}>×</button>
                </div>
              ))}
              <button type="button" className={styles.blockActionButton} onClick={() => setAssumptionsDraft([...assumptionsDraft, ""])}>+ Add</button>
              <div className={styles.blockActions} style={{ marginTop: 8 }}>
                <button
                  type="button"
                  className={styles.blockActionButton}
                  onClick={() => {
                    const cleaned = assumptionsDraft.map((item) => item.trim()).filter(Boolean);
                    onChange?.({
                      steps,
                      result,
                      verificationChecks,
                      finalAnswer,
                      assumptions: cleaned,
                      originalProblem,
                      normalizedProblem,
                    });
                    setEditingAssumptions(false);
                  }}
                >
                  Save
                </button>
                <button type="button" className={styles.blockActionButton} onClick={() => { setAssumptionsDraft(assumptions || []); setEditingAssumptions(false); }}>Cancel</button>
              </div>
            </div>
          ) : (
            <>
              <ul style={{ margin: 0, paddingLeft: 20, listStyleType: "disc", fontSize: 13, lineHeight: 1.6 }}>
                {assumptions.map((assumption, index) => (
                  <li key={`${sectionId}-assumption-${index}`} style={{ marginBottom: 4 }}>
                    <MathRenderer content={assumption} mode="prose" />
                  </li>
                ))}
              </ul>
              {editable && !exportMode && (
                <div className={styles.blockActions} style={{ marginTop: 8 }}>
                  <button type="button" className={styles.blockActionButton} onClick={() => setEditingAssumptions(true)}>Edit</button>
                </div>
              )}
            </>
          )}
        </SectionRow>
      )}

      {/* Steps */}
      {steps.map((step, index) => (
        <div key={`${sectionId}-step-${index}`} className={styles.stepRow} id={`${sectionId}-step-${index + 1}`}>
          <span className={styles.stepLabel}>STEP {step.k || index + 1}</span>
          <div className={styles.stepValue}>
            {editingStepIndex !== index ? (
              <span className={styles.stepTitleTag}>
                {step.titleRichHtml ? (
                  <div
                    className={styles.richTextElementContent}
                    style={{ fontWeight: 700, display: "inline-block" }}
                    dangerouslySetInnerHTML={{ __html: sanitizeRichTextHtml(step.titleRichHtml) }}
                  />
                ) : (
                  <strong>{!isGenericStepTitle(step.title, index) ? step.title : `Step ${step.k || index + 1}`}</strong>
                )}
              </span>
            ) : null}
            {editingStepIndex === index ? (
                <div className={styles.inlineEditWrap}>
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase" }}>Step Title</div>
                    <div data-testid={`step-title-editor-wrap-${sectionId}-${index}`} className={styles.inlineEditRichText} style={{ height: 60, minHeight: 60 }}>
                      <RichTextElementEditor
                        key={`${sectionId}-step-title-editor-${index}`}
                        elementId={`${sectionId}-step-title-${index}`}
                      initialText={stepDraft.title || ""}
                      initialHtml={stepDraft.titleRichHtml}
                      initialJson={stepDraft.titleRichJson}
                      onActivate={handleStepEditorActivate}
                      onCommit={handleStepTitleCommit}
                      onRequestClose={handleStepEditorRequestClose}
                    />
                  </div>
                  </div>
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase" }}>Explanation / Body</div>
                    <div data-testid={`step-explanation-editor-wrap-${sectionId}-${index}`} className={styles.inlineEditRichText} style={{ height: 140 }}>
                      <RichTextElementEditor
                        key={`${sectionId}-step-explanation-editor-${index}`}
                        elementId={`${sectionId}-step-explanation-${index}`}
                      initialText={stepDraft.explanation || ""}
                      initialHtml={stepDraft.explanationRichHtml}
                      initialJson={stepDraft.explanationRichJson}
                      onActivate={handleStepEditorActivate}
                      onCommit={handleStepExplanationCommit}
                      onRequestClose={handleStepEditorRequestClose}
                    />
                  </div>
                  </div>
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase" }}>Main Math / LaTeX</div>
                    <div data-testid={`step-math-editor-wrap-${sectionId}-${index}`} className={styles.inlineEditRichText} style={{ height: 100, minHeight: 80 }}>
                      <RichTextElementEditor
                        key={`${sectionId}-step-math-editor-${index}`}
                        elementId={`${sectionId}-step-math-${index}`}
                      initialText={stepDraft.mathLatex || ""}
                      initialHtml={stepDraft.mathRichHtml}
                      initialJson={stepDraft.mathRichJson}
                      onActivate={handleStepEditorActivate}
                      onCommit={handleStepMathCommit}
                      onRequestClose={handleStepEditorRequestClose}
                    />
                  </div>
                </div>
                <div className={styles.blockActions}>
                  <button data-testid={`step-save-${sectionId}-${index}`} type="button" className={styles.blockActionButton} onClick={saveStep}>Save</button>
                  <button type="button" className={styles.blockActionButton} onClick={() => setEditingStepIndex(null)}>Cancel</button>
                </div>
              </div>
            ) : (
              <>
                {step.explanationRichHtml ? (
                  <div
                    style={{ marginTop: 3, fontSize: 13, lineHeight: 1.6 }}
                    className={styles.richTextElementContent}
                    dangerouslySetInnerHTML={{ __html: sanitizeRichTextHtml(step.explanationRichHtml) }}
                  />
                ) : step.explanation ? (
                  <div style={{ marginTop: 3, fontSize: 13, lineHeight: 1.6 }}>
                    <MathRenderer content={step.explanation} mode="prose" />
                  </div>
                ) : step.bodyMarkdown ? (
                  <div style={{ marginTop: 3, fontSize: 13, lineHeight: 1.6 }}>
                    <MathRenderer content={step.bodyMarkdown} mode="prose" />
                  </div>
                ) : null}
                {step.mathRichHtml ? (
                  <div
                    style={{ marginTop: 8 }}
                    className={styles.richTextElementContent}
                    dangerouslySetInnerHTML={{ __html: sanitizeRichTextHtml(step.mathRichHtml) }}
                  />
                ) : step.mathLatex ? (
                  <div style={{ marginTop: 8 }}>
                    <MathRenderer content={step.mathLatex} mode="block" />
                  </div>
                ) : null}
                {editable && !exportMode && (
                  <div className={styles.blockActions} style={{ marginTop: 8 }}>
                    <button data-testid={`step-edit-${sectionId}-${index}`} type="button" className={styles.blockActionButton} onClick={() => startEditStep(index)}>Edit</button>
                    <button data-testid={`step-delete-${sectionId}-${index}`} type="button" className={styles.blockActionButton} onClick={() => deleteStep(index)}>Delete</button>
                  </div>
                )}
              </>
            )}

            {/* Step Metadata: Rules, Checks, Notes */}
            {editingStepIndex !== index && (
              <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                {step.rulesUsed && step.rulesUsed.length > 0 && (
                  <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                    <span style={{ fontWeight: 600, color: "var(--text-main)" }}>Rules: </span>
                    {step.rulesUsed.map((rule: string, i: number) => (
                      <React.Fragment key={i}>
                        <MathRenderer content={rule} mode="prose" />
                        {i < (step.rulesUsed?.length || 0) - 1 ? ", " : ""}
                      </React.Fragment>
                    ))}
                  </div>
                )}
                {step.checks && step.checks.length > 0 && (
                  <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                    <span style={{ fontWeight: 600, color: "var(--text-main)" }}>Checks: </span>
                    <ul style={{ margin: "4px 0 0", paddingLeft: 20, listStyleType: "circle" }}>
                      {step.checks.map((check: string, i: number) => (
                        <li key={i}>
                          <MathRenderer content={check} mode="prose" />
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {step.notes && (
                  <div style={{ fontSize: 12, color: "var(--text-muted)", fontStyle: "italic", background: "#f8fafc", padding: "8px 12px", borderRadius: 4, borderLeft: "3px solid #cbd5e1" }}>
                    <strong>Note:</strong> <MathRenderer content={step.notes} mode="inline" />
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      ))}

      {/* Final Answer Section */}
      <SectionRow label="FINAL ANSWER" id={`${sectionId}-final-answer`}>
        {editingResult ? (
          <div className={styles.inlineEditWrap}>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase" }}>Answer (LaTeX)</div>
              <textarea
                className={styles.inlineEditTextArea}
                style={{ minHeight: 60, width: "100%", fontFamily: "monospace" }}
                value={resultDraft}
                onChange={(e) => setResultDraft(e.target.value)}
              />
            </div>
            <div className={styles.blockActions}>
              <button
                data-testid={`final-save-${sectionId}`}
                type="button"
                className={styles.blockActionButton}
                onClick={() => {
                  onChange?.({
                    steps,
                    result: resultDraft,
                    verificationChecks,
                    finalAnswer: {
                      answer_text: finalAnswer?.answer_text || "",
                      answer_latex: resultDraft,
                      values: finalAnswer?.values || [],
                      units: finalAnswer?.units,
                    },
                    assumptions,
                    originalProblem,
                    normalizedProblem,
                  });
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
          <div style={{
            background: "linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)",
            border: "1px solid #e2e8f0",
            borderRadius: 12,
            padding: 20,
          }}>
            {/* Answer Text */}
            {displayAnswerText && (
              <div style={{ marginBottom: displayAnswerLatex || displayValues.length > 0 ? 16 : 0 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 8, letterSpacing: "0.05em" }}>
                  Summary
                </div>
                <div style={{ fontSize: 14, color: "#334155", lineHeight: 1.7 }}>
                  <MathRenderer content={displayAnswerText} mode="prose" />
                </div>
              </div>
            )}

            {/* Answer LaTeX - with deterministic line breaking */}
            {displayAnswerLatex && (() => {
              const blocks = parseLatexToBlocks(displayAnswerLatex);
              return (
                <div className={styles.finalAnswerMathContainer} style={{ marginBottom: displayValues.length > 0 ? 16 : 0 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 8, letterSpacing: "0.05em" }}>
                    Result
                  </div>
                  <div className={styles.finalAnswerMathContent}>
                    {blocks.map((block, idx) => (
                      block.kind === "math" ? (
                        <div key={idx} className={styles.finalAnswerMathBlock}>
                          <MathRenderer content={block.latex} mode="block" />
                        </div>
                      ) : (
                        <div key={idx} className={styles.finalAnswerTextBlock}>
                          {block.text}
                        </div>
                      )
                    ))}
                    {blocks.length === 0 && (
                      <div className={styles.finalAnswerMathBlock}>
                        <MathRenderer content={displayAnswerLatex} mode="block" />
                      </div>
                    )}
                  </div>
                </div>
              );
            })()}

            {/* Values */}
            {displayValues.length > 0 && (
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 12, letterSpacing: "0.05em" }}>
                  Values & Parameters
                </div>
                <div style={{ display: "grid", gap: 12 }}>
                  {displayValues.map((val, idx) => (
                    <div key={idx} style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 8, padding: 12 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: "#64748b", marginBottom: 6, textTransform: "capitalize" }}>
                        {val.label.replace(/_/g, " ")}
                      </div>
                      {val.value_latex ? (
                        <div style={{ fontSize: 14, color: "#0f172a" }}>
                          <MathRenderer content={val.value_latex} mode="inline" />
                        </div>
                      ) : (
                        <div style={{ fontSize: 13, color: "#475569", fontFamily: "monospace", whiteSpace: "pre-wrap" }}>
                          {typeof val.value === "string"
                            ? val.value
                            : (val.value === null || val.value === undefined)
                              ? "null"
                              : JSON.stringify(val.value, null, 2)
                          }
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Fallback if nothing */}
            {!displayAnswerText && !displayAnswerLatex && displayValues.length === 0 && (
              <div style={{ fontStyle: "italic", color: "var(--text-muted)" }}>No final answer provided.</div>
            )}

            {autocorrectApplied && (
              <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#15803d", fontWeight: 600 }}>
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>check_circle</span>
                Autocorrect Applied & Verified
              </div>
            )}

            {editable && !exportMode && (
              <div style={{ marginTop: 16 }}>
                <button data-testid={`final-edit-${sectionId}`} type="button" className={styles.blockActionButton} onClick={() => setEditingResult(true)}>
                  Edit
                </button>
              </div>
            )}
          </div>
        )}
      </SectionRow>

      {/* Verification */}
      {Array.isArray(verificationChecks) && verificationChecks.length > 0 && (
        <SectionRow label="VERIFY" id={`${sectionId}-verification`}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Verification:</div>
          {verificationChecks.map((check, index) => (
            <div key={`${check.checkId}-${index}`} style={{ marginBottom: index < verificationChecks.length - 1 ? 8 : 0 }}>
              <div style={{ fontWeight: 600 }}>{check.checkId} ({check.verdict.toUpperCase()})</div>
              <div style={{ fontSize: 13, lineHeight: 1.6 }}>{check.message}</div>
              {check.evidenceMath && (
                <div style={{ marginTop: 4 }}>
                  <MathRenderer content={check.evidenceMath} mode="inline" />
                </div>
              )}
            </div>
          ))}
        </SectionRow>
      )}

      {/* Common Mistakes */}
      {Array.isArray(commonMistakes) && commonMistakes.length > 0 && (
        <SectionRow label="MISTAKES" id={`${sectionId}-mistakes`} style={{ borderLeft: "3px solid #f59e0b", background: "#fffbeb" }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#b45309", marginBottom: 8, textTransform: "uppercase" }}>Common Mistakes to Avoid</div>
          <ul style={{ margin: 0, paddingLeft: 20, listStyleType: "disc", fontSize: 13, color: "#92400e", lineHeight: 1.6 }}>
            {commonMistakes.map((mistake, index) => (
              <li key={`${sectionId}-mistake-${index}`} style={{ marginBottom: 4 }}>
                {mistake}
              </li>
            ))}
          </ul>
        </SectionRow>
      )}
    </div>
  );
}
