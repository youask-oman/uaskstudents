"use client";

import React from "react";
import type { Editor } from "@tiptap/core";
import MathRenderer from "@/components/math/MathJaxRenderer";
import RichTextElementEditor from "./RichTextElementEditor";
import type { RichTextCommitPayload } from "./RichTextElementEditor";
import { StepRow, VerificationCheck, FinalAnswer, ShortSection, ShortSourcePayload } from "./types";
import { parseLatexToBlocks } from "@/lib/final-answer-layout-engine";
import { useMathOverflowFix } from "@/hooks/useMathOverflowFix";
import styles from "./MathCanvas.module.css";

interface SolutionStepsBlockProps {
  steps: StepRow[];
  shortSections?: ShortSection[];
  shortSource?: ShortSourcePayload;
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
  hideStepLabels?: boolean;
  finalHandwritten?: boolean;
  shortPaper?: boolean;
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

const looksLikeMathExpression = (value: string): boolean => {
  const text = (value || "").trim();
  if (!text) return false;
  if (text.includes("\\(") || text.includes("\\[") || text.includes("$$")) return true;
  if (/\\[a-zA-Z]+/.test(text)) return true;
  const hasMathOps = /[=^_<>+\-*/]/.test(text);
  const words = (text.match(/[A-Za-z]{3,}/g) || []).length;
  return hasMathOps && words <= 2;
};

const hasStandaloneMathDelimiters = (text: string): boolean => {
  const trimmed = (text || "").trim();
  if (!trimmed) return false;
  if ((trimmed.startsWith("\\(") && trimmed.endsWith("\\)")) || (trimmed.startsWith("\\[") && trimmed.endsWith("\\]"))) {
    return true;
  }
  if ((trimmed.startsWith("$$") && trimmed.endsWith("$$")) || (trimmed.startsWith("$") && trimmed.endsWith("$"))) {
    return true;
  }
  return false;
};

const shouldRenderAsProse = (value: string): boolean => {
  const text = (value || "").trim();
  if (!text) return false;
  if (hasStandaloneMathDelimiters(text)) return false;
  if (/^\\begin\{(?:aligned|align|gather|equation|cases|pmatrix|bmatrix|matrix)\}/.test(text)) return false;

  const hasMathCommand = /\\[a-zA-Z]+/.test(text);
  const hasMathOperators = /[=^_<>+\-*/]/.test(text);
  const hasBraces = /[{}]/.test(text);
  const plainWordCount = (text.match(/(?<!\\)\b[A-Za-z]{3,}\b/g) || []).length;

  // Pure prose (no math signals) should always render as prose.
  if (!hasMathCommand && !hasMathOperators && !hasBraces) return true;

  // Command-heavy LaTeX with no natural-language words should remain math.
  if (hasMathCommand && plainWordCount === 0) return false;

  // Mixed prose + math should render as prose to preserve spacing.
  if (plainWordCount >= 3) return true;

  // Short equation-like snippets should remain math.
  return false;
};

const normalizeValueLabel = (value: string): string => (value || "").replace(/_/g, " ").trim();

const wrapProblemMath = (value: string): string => {
  const text = (value || "")
    .trim()
    .replace(/\\\\\(/g, "\\(")
    .replace(/\\\\\)/g, "\\)")
    .replace(/\\\\\[/g, "\\[")
    .replace(/\\\\\]/g, "\\]");
  if (!text) return "";
  if (text.includes("\\(") || text.includes("\\[") || text.includes("$")) return text;

  const inverseMatch = text.match(/^(Find\s+the\s+inverse\s+of\s+)(.+)$/i);
  if (inverseMatch) {
    return `${inverseMatch[1]}\\(${inverseMatch[2].trim()}\\)`;
  }

  const inlineEquation = /([A-Za-z][A-Za-z0-9_]*\([^)]*\)\s*=\s*[^,.;\n]+|[A-Za-z][A-Za-z0-9_]*\s*=\s*[^,.;\n]+)/;
  if (inlineEquation.test(text)) {
    return text.replace(inlineEquation, (expr) => `\\(${expr.trim()}\\)`);
  }

  return text;
};

/* Section row component for consistent alignment */
const SectionRow: React.FC<{ label: string; id: string; style?: React.CSSProperties; children: React.ReactNode; hideLabel?: boolean }> = ({ label, id, style, children, hideLabel }) => (
  <div className={styles.stepRow} id={id} style={style}>
    {!hideLabel ? <span className={styles.stepLabel}>{label}</span> : null}
    <div className={styles.stepValue} style={hideLabel ? { gridColumn: "1 / -1" } : undefined}>{children}</div>
  </div>
);

export default function SolutionStepsBlock({
  steps,
  shortSections,
  shortSource,
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
  hideStepLabels = false,
  finalHandwritten = false,
  shortPaper = false,
  onActiveTextEditorChange,
  onChange,
}: SolutionStepsBlockProps) {
  const problemSectionLabel = shortPaper ? "QUESTION Q1" : "PROBLEM";
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
  const hasShortSections = shortPaper && Array.isArray(shortSections) && shortSections.length > 0;
  const hasShortSource = shortPaper && Array.isArray(shortSource?.sections) && shortSource.sections.length > 0;

  if (finalHandwritten) {
    const finalValue = displayAnswerLatex || displayAnswerText || result || "";
    const finalMode = shouldRenderAsProse(finalValue) ? "prose" : "block";
    return (
      <div className={styles.stepsBlockFinalHandwritten} ref={rootRef}>
        <div className={styles.finalDividerFinalHandwritten} />
        <div className={styles.resultMetaFinalHandwritten}>RESULT</div>
        <div className={styles.resultContentFinalHandwritten}>
          <MathRenderer content={finalValue} mode={finalMode} />
        </div>
      </div>
    );
  }

  if (hasShortSections) {
    return (
      <div className={styles.stepsBlock} ref={rootRef}>
        {(originalProblem || normalizedProblem) && (
          <SectionRow label={problemSectionLabel} id={`${sectionId}-problem`} hideLabel={false}>
            <div style={{ whiteSpace: "pre-wrap", fontSize: 13, color: "var(--text-main)", lineHeight: 1.6 }}>
              <MathRenderer content={wrapProblemMath(normalizedProblem || originalProblem || "")} mode="prose" />
            </div>
          </SectionRow>
        )}

        {shortSections.map((section, sectionIndex) => (
          <SectionRow
            key={`${sectionId}-section-${sectionIndex}`}
            label={(section.heading || section.label || `(${sectionIndex + 1})`).toUpperCase()}
            id={`${sectionId}-section-${sectionIndex}`}
            hideLabel={false}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {section.steps.map((step, stepIndex) => (
                <div key={`${sectionId}-section-${sectionIndex}-step-${stepIndex}`} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                    Step {step.index}
                  </div>
                  {Array.isArray(step.blocks) && step.blocks.length > 0 ? (
                    step.blocks.map((block, blockIndex) => (
                      <div key={`${sectionId}-section-${sectionIndex}-step-${stepIndex}-block-${blockIndex}`}>
                        <MathRenderer
                          content={block.content}
                          mode={String(block.kind).toLowerCase() === "math" ? "block" : "prose"}
                        />
                      </div>
                    ))
                  ) : step.raw ? (
                    <MathRenderer content={step.raw} mode="prose" />
                  ) : null}
                </div>
              ))}

              {section.finalAnswer ? (
                <div style={{ marginTop: 4 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 6 }}>
                    Section Final
                  </div>
                  <MathRenderer content={section.finalAnswer} mode={shouldRenderAsProse(section.finalAnswer) ? "prose" : "block"} />
                </div>
              ) : null}
            </div>
          </SectionRow>
        ))}

        <SectionRow label="RESULT" id={`${sectionId}-final-answer`} hideLabel={false}>
          {displayAnswerLatex || displayAnswerText ? (
            <MathRenderer content={displayAnswerLatex || displayAnswerText} mode={shouldRenderAsProse(displayAnswerLatex || displayAnswerText) ? "prose" : "block"} />
          ) : (
            <div style={{ fontStyle: "italic", color: "var(--text-muted)" }}>No final answer provided.</div>
          )}
        </SectionRow>
      </div>
    );
  }

  if (hasShortSource) {
    const globalFinal = (shortSource?.global_final_answer || "").trim();
    return (
      <div className={styles.stepsBlock} ref={rootRef}>
        {shortSource.sections.map((section, sectionIndex) => {
          const label = (section.heading || section.label || `(${sectionIndex + 1})`).toString();
          const sectionSteps = Array.isArray(section.steps) ? section.steps : [];
          return (
            <SectionRow
              key={`${sectionId}-source-section-${sectionIndex}`}
              label={label.toUpperCase()}
              id={`${sectionId}-source-section-${sectionIndex}`}
              hideLabel={false}
            >
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {sectionSteps.map((step, stepIndex) => {
                  const stepBlocks = Array.isArray(step.blocks) ? step.blocks : [];
                  const stepIndexDisplay = Number.isFinite(Number(step.index)) ? Number(step.index) : stepIndex + 1;
                  return (
                    <div key={`${sectionId}-source-section-${sectionIndex}-step-${stepIndex}`} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                        Step {stepIndexDisplay}
                      </div>
                      {stepBlocks.length > 0 ? stepBlocks.map((block, blockIndex) => {
                        const content = String(block?.content || "").trim();
                        if (!content) return null;
                        const kind = String(block?.kind || "text").toLowerCase();
                        if (kind !== "math") {
                          const lines = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
                          return (
                            <div key={`${sectionId}-source-section-${sectionIndex}-step-${stepIndex}-block-${blockIndex}`}>
                              {lines.map((line, lineIndex) => (
                                <div key={`${sectionId}-source-section-${sectionIndex}-step-${stepIndex}-block-${blockIndex}-line-${lineIndex}`} style={{ whiteSpace: "pre-wrap" }}>
                                  {line.trim().length === 0 ? "\u00A0" : <MathRenderer content={line} mode="prose" />}
                                </div>
                              ))}
                            </div>
                          );
                        }
                        return (
                          <div key={`${sectionId}-source-section-${sectionIndex}-step-${stepIndex}-block-${blockIndex}`}>
                            <MathRenderer content={content} mode="block" />
                          </div>
                        );
                      }) : step.raw ? (
                        <div>
                          {String(step.raw).replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n").map((line, lineIndex) => (
                            <div key={`${sectionId}-source-section-${sectionIndex}-step-${stepIndex}-raw-${lineIndex}`} style={{ whiteSpace: "pre-wrap" }}>
                              {line.trim().length === 0 ? "\u00A0" : <MathRenderer content={line} mode="prose" />}
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  );
                })}

                {section.final_answer ? (
                  <div style={{ marginTop: 4 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 6 }}>
                      Section Final
                    </div>
                    <MathRenderer content={section.final_answer} mode={shouldRenderAsProse(section.final_answer) ? "prose" : "block"} />
                  </div>
                ) : null}
              </div>
            </SectionRow>
          );
        })}

        <SectionRow label="RESULT" id={`${sectionId}-final-answer`} hideLabel={false}>
          {globalFinal ? (
            <MathRenderer content={globalFinal} mode={shouldRenderAsProse(globalFinal) ? "prose" : "block"} />
          ) : (
            <div style={{ fontStyle: "italic", color: "var(--text-muted)" }}>No final answer provided.</div>
          )}
        </SectionRow>
      </div>
    );
  }

  return (
    <div className={styles.stepsBlock} ref={rootRef}>
      {/* Domain Constraints */}
      {Array.isArray(domainConstraints) && domainConstraints.length > 0 && (
        <SectionRow label="DOMAIN" id={`${sectionId}-domain`} hideLabel={hideStepLabels}>
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
        <SectionRow label={problemSectionLabel} id={`${sectionId}-problem`} hideLabel={hideStepLabels}>
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
              <div style={{ whiteSpace: "pre-wrap", fontSize: 13, color: "var(--text-main)", lineHeight: 1.6 }}>
                <MathRenderer content={wrapProblemMath(normalizedProblem || originalProblem || "")} mode="prose" />
              </div>
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
        <SectionRow label="ASSUMPTIONS" id={`${sectionId}-assumptions`} hideLabel={hideStepLabels}>
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
              <ul
                style={{
                  margin: 0,
                  paddingInlineStart: 20,
                  listStyleType: "disc",
                  fontSize: 13,
                  lineHeight: 1.6,
                }}
              >
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
          {!hideStepLabels ? <span className={styles.stepLabel}>STEP {step.k || index + 1}</span> : null}
          <div className={styles.stepValue} style={hideStepLabels ? { gridColumn: "1 / -1" } : undefined}>
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
                    <MathRenderer content={step.mathLatex} mode={shouldRenderAsProse(step.mathLatex) ? "prose" : "block"} />
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
      <SectionRow label={shortPaper ? "RESULT" : "FINAL ANSWER"} id={`${sectionId}-final-answer`} hideLabel={false}>
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
            background: "transparent",
            border: "0",
            borderRadius: 0,
            padding: 2,
          }}>
            {/* Answer Text */}
            {displayAnswerText && (
              <div style={{ marginBottom: displayAnswerLatex || displayValues.length > 0 ? 16 : 0 }}>
                {!hideStepLabels ? (
                  <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 8, letterSpacing: "0.05em" }}>
                    Summary
                  </div>
                ) : null}
                <div style={{ fontSize: 14, color: "#0f172a", fontWeight: 700, lineHeight: 1.7 }}>
                  <MathRenderer content={displayAnswerText} mode={looksLikeMathExpression(displayAnswerText) ? "inline" : "prose"} />
                </div>
              </div>
            )}

            {/* Answer LaTeX - with deterministic line breaking */}
            {displayAnswerLatex && shouldRenderAsProse(displayAnswerLatex) ? (
              <div className={styles.finalAnswerMathContainer} style={{ marginBottom: displayValues.length > 0 ? 16 : 0 }}>
                {!hideStepLabels ? (
                  <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 8, letterSpacing: "0.05em" }}>
                    Result
                  </div>
                ) : null}
                <div className={styles.finalAnswerTextBlock}>
                  <MathRenderer content={displayAnswerLatex} mode="prose" />
                </div>
              </div>
            ) : displayAnswerLatex && (() => {
              const blocks = parseLatexToBlocks(displayAnswerLatex);
              return (
                <div className={styles.finalAnswerMathContainer} style={{ marginBottom: displayValues.length > 0 ? 16 : 0 }}>
                  {!hideStepLabels ? (
                    <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 8, letterSpacing: "0.05em" }}>
                      Result
                    </div>
                  ) : null}
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
                    <div key={idx} style={{ background: "transparent", border: "1px solid #dbe3ee", borderRadius: 8, padding: 12 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: "#64748b", marginBottom: 6 }}>
                        {looksLikeMathExpression(normalizeValueLabel(val.label)) ? (
                          <MathRenderer content={normalizeValueLabel(val.label)} mode="inline" />
                        ) : (
                          normalizeValueLabel(val.label)
                        )}
                      </div>
                      {val.value_latex ? (
                        <div style={{ fontSize: 14, color: "#0f172a", fontWeight: 700 }}>
                          <MathRenderer content={val.value_latex} mode="inline" />
                        </div>
                      ) : (
                        <div style={{ fontSize: 13, color: "#0f172a", fontWeight: 700, fontFamily: "monospace", whiteSpace: "pre-wrap" }}>
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
        <SectionRow label="VERIFY" id={`${sectionId}-verification`} hideLabel={hideStepLabels}>
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
        <SectionRow label="MISTAKES" id={`${sectionId}-mistakes`} hideLabel={hideStepLabels} style={{ borderLeft: "3px solid #f59e0b", background: "#fffbeb" }}>
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
