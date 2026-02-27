import type { SessionMessage } from "@/components/math-canvas/types";

export type PlaybackSegmentKind = "step_title" | "markdown" | "math" | "final_answer";

export interface PlaybackSegment {
  kind: PlaybackSegmentKind;
  text: string;
}

export interface PlaybackResolution {
  source:
    | "solutions_steps"
    | "items_steps"
    | "message.display_markdown"
    | "message.rendered_content"
    | "structured.display_markdown"
    | "structured.rendered_content"
    | "structured.response.message.content"
    | "structured.response.response"
    | "synthesized_from_sections"
    | "message.content"
    | "none";
  content: string;
  segments: PlaybackSegment[];
  questionId?: string;
}

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" ? (value as Record<string, unknown>) : null;

const asString = (value: unknown): string =>
  typeof value === "string"
    ? value
    : (typeof value === "number" || typeof value === "boolean" ? String(value) : "");

const PROTOCOL_MARKER_RE =
  /(?:^|[^A-Za-z0-9_])(?:BEGIN_SOLUTION|BEGIN_STEPS|END_STEPS|BEGIN_FINAL|END_FINAL|END_SOLUTION|begin_solution|begin_steps|end_steps|begin_final|end_final|end\(\s*final\s*\)|end_solution)(?=$|[^A-Za-z0-9_])/gi;

export const stripProtocolMarkers = (value: string): string => {
  const normalized = (value || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const withoutMarkers = normalized.replace(PROTOCOL_MARKER_RE, (match) => {
    const first = match[0] || "";
    return /[A-Za-z0-9_]/.test(first) ? "" : first;
  });
  return withoutMarkers
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
};

const sanitizeInline = (value: unknown): string => stripProtocolMarkers(asString(value));

const normalizeMathTokenForCompare = (value: string): string =>
  stripProtocolMarkers(value)
    .replace(/\\\(|\\\)|\\\[|\\\]/g, "")
    .replace(/\$/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();

const hasBrokenInlineTextMath = (value: string): boolean => {
  const text = stripProtocolMarkers(value || "");
  if (!text) return false;
  if (/[A-Za-z]{2,}\([^)]*\)[A-Za-z]{2,}/.test(text)) return true;
  if (/,/.test(text) && /=/.test(text) && (text.match(/[A-Za-z]{4,}/g) || []).length >= 3) return true;
  return false;
};

const normalizeBrokenInlineTextMath = (value: string): string =>
  stripProtocolMarkers(value || "")
    .replace(/([A-Za-z]{2,})\(/g, "$1 (")
    .replace(/\)([A-Za-z]{2,})/g, ") $1")
    .replace(/,\s*(?=[A-Za-z]\([^)]*\)\s*=)/g, ",\n")
    .replace(/\s{2,}/g, " ")
    .trim();

const collectCommonMistakes = (node: Record<string, unknown> | null | undefined): string[] => {
  if (!node) return [];
  const quality = asRecord(node.quality);
  const mistakes = Array.isArray(quality?.common_mistakes) ? quality?.common_mistakes : [];
  return mistakes
    .map((item) => sanitizeInline(item))
    .map((item) => normalizeBrokenInlineTextMath(item))
    .filter((item) => item.length > 0);
};

const buildSegmentsFromSolutions = (structured: Record<string, unknown>): PlaybackResolution | null => {
  const solutions = Array.isArray(structured.solutions) ? structured.solutions : [];
  if (!solutions.length) return null;
  const segments: PlaybackSegment[] = [];

  const questionNode = asRecord(structured.question);
  const questions = Array.isArray(structured.questions) ? structured.questions : [];
  const targetQuestionId =
    sanitizeInline(questionNode?.question_id) ||
    sanitizeInline(asRecord(questions[0])?.question_id);

  const solution = (solutions
    .map((item) => asRecord(item))
    .find((item) => item && targetQuestionId && sanitizeInline(item.question_id) === targetQuestionId) ||
    solutions.map((item) => asRecord(item)).find(Boolean)) as Record<string, unknown> | undefined;
  if (!solution) return null;

  const questionId = sanitizeInline(solution.question_id || targetQuestionId || "q1") || "q1";
  segments.push({ kind: "markdown", text: `### ${questionId.toUpperCase()} (${questionId})` });

  const steps = Array.isArray(solution.steps) ? solution.steps : [];
  steps.forEach((rawStep, idx) => {
    const step = asRecord(rawStep);
    if (!step) return;
    const explanation =
      sanitizeInline(step.explanation) ||
      sanitizeInline(step.raw) ||
      sanitizeInline(step.text) ||
      sanitizeInline(step.work);
    const explanationNorm = normalizeMathTokenForCompare(explanation);
    const math = Array.isArray(step.math_latex) ? step.math_latex : [];
    const uniqueMath = math
      .map((m) => sanitizeInline(m))
      .filter(Boolean)
      .filter((m) => {
        const token = normalizeMathTokenForCompare(m);
        if (!token) return false;
        return !explanationNorm || !explanationNorm.includes(token);
      });

    if (!explanation && uniqueMath.length === 0) return;

    const stepIndex = Number(step.index);
    const heading = sanitizeInline(step.title) || `Step ${Number.isFinite(stepIndex) ? stepIndex : idx + 1}`;
    if (heading) {
      segments.push({ kind: "step_title", text: heading });
    }
    if (explanation) {
      segments.push({ kind: "markdown", text: explanation });
    }
    uniqueMath.forEach((text) => {
      segments.push({ kind: "math", text });
    });
  });

  const finalAnswer = asRecord(solution.final_answer);
  const finalText =
    sanitizeInline(finalAnswer?.answer_latex) ||
    sanitizeInline(finalAnswer?.answer_text) ||
    sanitizeInline(solution.result);
  if (finalText) {
    segments.push({ kind: "final_answer", text: finalText });
  }

  const mistakes = collectCommonMistakes(solution);
  if (mistakes.length > 0) {
    segments.push({ kind: "step_title", text: "Common Mistakes" });
    mistakes.forEach((mistake) => segments.push({ kind: "markdown", text: `- ${mistake}` }));
  }

  if (!segments.length) return null;
  const content = segmentsToMarkdown(segments);
  return {
    source: "solutions_steps",
    content,
    segments,
    questionId,
  };
};

const buildSegmentsFromItems = (structured: Record<string, unknown>): PlaybackResolution | null => {
  const items = Array.isArray(structured.items) ? structured.items : [];
  if (!items.length) return null;

  const parsedItems = items.map((raw) => asRecord(raw)).filter((row): row is Record<string, unknown> => Boolean(row));
  if (!parsedItems.length) return null;

  const segments: PlaybackSegment[] = [];
  const trailingCommonMistakes: string[] = [];
  const firstQuestionId = sanitizeInline(parsedItems[0]?.question_id || "q1") || "q1";

  parsedItems.forEach((item, idx) => {
    const questionId = sanitizeInline(item.question_id || `q${idx + 1}`) || `q${idx + 1}`;
    const questionText = sanitizeInline(item.question_text);
    const heading = questionText
      ? `### ${questionId.toUpperCase()} (${questionId})\n${questionText}`
      : `### ${questionId.toUpperCase()} (${questionId})`;
    segments.push({ kind: "markdown", text: heading });

    const steps = Array.isArray(item.steps) ? item.steps : [];
    steps.forEach((rawStep, stepIdx) => {
      const step = asRecord(rawStep);
      if (!step) return;
      const stepIndex = Number(step.index);
      const stepHeading = sanitizeInline(step.title) || `Step ${Number.isFinite(stepIndex) ? stepIndex : stepIdx + 1}`;
      if (stepHeading) {
        segments.push({ kind: "step_title", text: stepHeading });
      }
      const blocks = Array.isArray(step.blocks) ? step.blocks : [];
      blocks.forEach((rawBlock) => {
        const block = asRecord(rawBlock);
        if (!block) return;
        const text = sanitizeInline(block.content);
        if (!text) return;
        const kind = sanitizeInline(block.kind).toLowerCase();
        if (kind === "math") {
          segments.push({ kind: "math", text });
          return;
        }
        segments.push({ kind: "markdown", text });
      });
    });

    const finalAnswer = asRecord(item.final_answer);
    const finalText =
      sanitizeInline(finalAnswer?.answer_latex) ||
      sanitizeInline(finalAnswer?.answer_text) ||
      sanitizeInline(item.answer_latex) ||
      sanitizeInline(item.answer_text);
    if (finalText) {
      segments.push({ kind: "final_answer", text: finalText });
    }
    trailingCommonMistakes.push(...collectCommonMistakes(item));
  });

  const uniqueMistakes = [...new Set(trailingCommonMistakes.map((m) => m.trim()).filter(Boolean))];
  if (uniqueMistakes.length > 0) {
    segments.push({ kind: "step_title", text: "Common Mistakes" });
    uniqueMistakes.forEach((mistake) => segments.push({ kind: "markdown", text: `- ${mistake}` }));
  }

  if (!segments.length) return null;
  const content = segmentsToMarkdown(segments);
  return {
    source: "items_steps",
    content,
    segments,
    questionId: firstQuestionId,
  };
};

const synthesizeFromSections = (structured: Record<string, unknown>): string => {
  const candidate = asRecord(structured.raw_user_extraction) || structured;
  const sections = Array.isArray(candidate.sections) ? candidate.sections : [];
  if (!sections.length) return "";
  const lines: string[] = [];
  sections.forEach((section, sectionIndex) => {
    const sectionObj = asRecord(section);
    if (!sectionObj) return;
    const heading =
      sanitizeInline(sectionObj.heading) ||
      sanitizeInline(sectionObj.label) ||
      `Section ${sectionIndex + 1}`;
    if (heading) lines.push(heading);
    const steps = Array.isArray(sectionObj.steps) ? sectionObj.steps : [];
    steps.forEach((step, stepIndex) => {
      const stepObj = asRecord(step);
      if (!stepObj) return;
      const rawIndex = Number(stepObj.index);
      const stepNumber = Number.isFinite(rawIndex) ? rawIndex : stepIndex + 1;
      lines.push(`Step ${stepNumber}`);
      const stepBlocks = Array.isArray(stepObj.blocks) ? stepObj.blocks : [];
      if (stepBlocks.length > 0) {
        stepBlocks.forEach((block) => {
          const blockObj = asRecord(block);
          if (!blockObj) return;
          const content = sanitizeInline(blockObj.content);
          if (content) lines.push(content);
        });
      } else {
        const rawStep = sanitizeInline(stepObj.raw);
        if (rawStep) lines.push(rawStep);
      }
    });
    const sectionFinal = sanitizeInline(sectionObj.final_answer);
    if (sectionFinal) {
      lines.push("Section Final");
      lines.push(sectionFinal);
    }
  });
  return stripProtocolMarkers(lines.filter(Boolean).join("\n\n"));
};

export const segmentsToMarkdown = (segments: PlaybackSegment[]): string => {
  const isLikelyLatex = (value: string): boolean => {
    const text = (value || "").trim();
    if (!text) return false;
    if (text.startsWith("\\(") || text.startsWith("\\[") || text.startsWith("$$")) return true;
    if (text.includes("\\boxed") || /\\[a-zA-Z]+/.test(text)) return true;
    return false;
  };

  const lines: string[] = [];
  segments.forEach((seg) => {
    const text = stripProtocolMarkers(seg.text);
    if (!text) return;
    if (seg.kind === "step_title") {
      lines.push(`#### ${text}`);
      lines.push("");
      return;
    }
    if (seg.kind === "math") {
      if (hasBrokenInlineTextMath(text)) {
        lines.push(normalizeBrokenInlineTextMath(text));
      } else {
        const mathBlock = text.startsWith("\\[") || text.startsWith("$$") ? text : `\\[\n${text}\n\\]`;
        lines.push(mathBlock);
      }
      lines.push("");
      return;
    }
    if (seg.kind === "final_answer") {
      const finalText = isLikelyLatex(text) && !text.startsWith("\\(") && !text.startsWith("\\[") && !text.startsWith("$$")
        ? `\\(${text}\\)`
        : text;
      lines.push(`**Final Answer:** ${finalText}`);
      lines.push("");
      return;
    }
    lines.push(text);
    lines.push("");
  });
  return stripProtocolMarkers(lines.join("\n"));
};

export const resolvePlaybackFromMessage = (message: SessionMessage): PlaybackResolution => {
  const structured = asRecord(message?.structured_data) || {};
  const fromSolutions = buildSegmentsFromSolutions(structured);
  if (fromSolutions) return fromSolutions;
  const fromItems = buildSegmentsFromItems(structured);
  if (fromItems) return fromItems;

  const responseNode = asRecord(structured.response);
  const responseMessage = asRecord(responseNode?.message);
  const candidates: Array<{ source: PlaybackResolution["source"]; value: string }> = [
    { source: "message.display_markdown", value: sanitizeInline((message as SessionMessage).display_markdown) },
    { source: "message.rendered_content", value: sanitizeInline((message as SessionMessage).rendered_content) },
    { source: "structured.display_markdown", value: sanitizeInline(structured.display_markdown) },
    { source: "structured.rendered_content", value: sanitizeInline(structured.rendered_content) },
    { source: "structured.response.message.content", value: sanitizeInline(responseMessage?.content) },
    { source: "structured.response.response", value: sanitizeInline(responseNode?.response) },
    { source: "synthesized_from_sections", value: synthesizeFromSections(structured) },
    { source: "message.content", value: sanitizeInline(message?.content) },
  ];
  for (const candidate of candidates) {
    if (candidate.value) {
      return {
        source: candidate.source,
        content: candidate.value,
        segments: [{ kind: "markdown", text: candidate.value }],
      };
    }
  }
  return { source: "none", content: "", segments: [] };
};
