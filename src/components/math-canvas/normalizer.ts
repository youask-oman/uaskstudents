import {
  ChartPayload,
  MathSolutionPayload,
  NormalizedChatMessage,
  SessionMessage,
  ShortSection,
  StepRow,
  VerificationCheck,
} from "./types";

const JSON_SIZE_LIMIT = 200_000;

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" ? (value as Record<string, unknown>) : null;

const asString = (value: unknown): string | null => {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return null;
};

const asStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => asString(item)?.trim() || "")
    .filter((item) => item.length > 0);
};

const getHintsList = (obj: Record<string, unknown>): Array<Record<string, unknown>> => {
  const direct = obj.hints;
  const spaced = obj[" hints"];
  const value = Array.isArray(direct) ? direct : Array.isArray(spaced) ? spaced : [];
  return value
    .map((item, index) => {
      const asObj = asRecord(item);
      if (asObj) return asObj;
      const asText = asString(item);
      if (asText) {
        return {
          key: `step_${index + 1}`,
          value: asText,
        } as Record<string, unknown>;
      }
      return null;
    })
    .filter((item): item is Record<string, unknown> => item !== null);
};

const parsePointArray = (value: unknown): ChartPayload["points"] => {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      const point = asRecord(item);
      if (!point) return null;
      const x = Number(point.x);
      const y = Number(point.y);
      if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
      return {
        x,
        y,
        label: asString(point.label) || undefined,
      };
    })
    .filter((item): item is NonNullable<typeof item> => item !== null);
};

const parseSeriesXYArray = (entry: Record<string, unknown>): ChartPayload["points"] => {
  const xs = Array.isArray(entry.x) ? entry.x : [];
  const ys = Array.isArray(entry.y) ? entry.y : [];
  const points: ChartPayload["points"] = [];
  const length = Math.min(xs.length, ys.length, 500);
  for (let i = 0; i < length; i += 1) {
    const x = Number(xs[i]);
    const y = Number(ys[i]);
    if (Number.isFinite(x) && Number.isFinite(y)) {
      points.push({ x, y });
    }
  }
  return points;
};

const parseLayoutTitleFromObject = (value: unknown): string | undefined => {
  const obj = asRecord(value);
  if (!obj) return undefined;
  const layout = asRecord(obj.layout);
  if (!layout) return undefined;
  return (
    asString(layout[".title"]) ||
    asString(layout.title) ||
    asString(asRecord(layout.title)?.text) ||
    undefined
  );
};

const parsePlotlySpecPoints = (value: unknown): ChartPayload["points"] => {
  const spec = asRecord(value);
  if (!spec) return [];
  const data = Array.isArray(spec.data) ? spec.data : [];
  for (const traceLike of data) {
    const trace = asRecord(traceLike);
    if (!trace) continue;
    const xs = Array.isArray(trace.x) ? trace.x : [];
    const ys = Array.isArray(trace.y) ? trace.y : [];
    const points: ChartPayload["points"] = [];
    const length = Math.min(xs.length, ys.length, 200);
    for (let i = 0; i < length; i += 1) {
      const x = Number(xs[i]);
      const y = Number(ys[i]);
      if (Number.isFinite(x) && Number.isFinite(y)) {
        points.push({ x, y });
      }
    }
    if (points.length >= 2) return points;
  }
  return [];
};

const parseDirectPlotlyChart = (value: unknown): ChartPayload | null => {
  const spec = asRecord(value);
  if (!spec) return null;
  const points = parsePlotlySpecPoints(spec);
  if (points.length < 2) return null;

  const layout = asRecord(spec.layout);
  const xAxis = asRecord(layout?.xaxis);
  const yAxis = asRecord(layout?.yaxis);
  const titleValue =
    asString(layout?.[".title"]) ||
    asString(layout?.title) ||
    asString(asRecord(layout?.title)?.text) ||
    "Graph";
  const xLabel = asString(xAxis?.title) || asString(asRecord(xAxis?.title)?.text) || "x";
  const yLabel = asString(yAxis?.title) || asString(asRecord(yAxis?.title)?.text) || "y";

  return {
    title: titleValue,
    xLabel,
    yLabel,
    points,
  };
};

const parsePlotFromObject = (value: unknown): ChartPayload[] => {
  const obj = asRecord(value);
  if (!obj) return [];
  const layoutTitle = parseLayoutTitleFromObject(obj);

  const directPlotly = parseDirectPlotlyChart(obj);
  if (directPlotly) {
    return [{ ...directPlotly, title: layoutTitle || directPlotly.title }];
  }

  const plotObject = asRecord(obj.plot);
  const plotSpecs = Array.isArray(plotObject?.plot_specs) ? plotObject?.plot_specs : [];
  const parsedFromPlotSpecs: ChartPayload[] = [];
  plotSpecs.forEach((specLike, index) => {
    const specEntry = asRecord(specLike);
    if (!specEntry) return;
    const specPoints = parsePlotlySpecPoints(specEntry.spec);
    if (specPoints.length < 2) return;
    parsedFromPlotSpecs.push({
      title: layoutTitle || asString(specEntry.plot_id) || `Plot ${index + 1}`,
      xLabel: "x",
      yLabel: "y",
      points: specPoints,
    });
  });
  if (parsedFromPlotSpecs.length > 0) return parsedFromPlotSpecs;

  const directPlotSpecs = Array.isArray(obj.plot_specs) ? obj.plot_specs : [];
  if (directPlotSpecs.length > 0) {
    const mappedDirectSpecs: ChartPayload[] = [];
    directPlotSpecs.forEach((specLike, index) => {
      const specEntry = asRecord(specLike);
      if (!specEntry) return;
      const directSpec = parseDirectPlotlyChart(specEntry.spec ?? specEntry);
      if (!directSpec) return;
      mappedDirectSpecs.push({
        ...directSpec,
        title: layoutTitle || asString(specEntry.plot_id) || directSpec.title || `Plot ${index + 1}`,
      });
    });
    if (mappedDirectSpecs.length > 0) return mappedDirectSpecs;
  }

  const plotsValue = asRecord(obj.visuals)?.plots ?? obj.plots ?? obj.plot;
  const plots = Array.isArray(plotsValue) ? plotsValue : plotsValue ? [plotsValue] : [];

  const parsed: ChartPayload[] = [];
  plots.forEach((plotLike) => {
    const plot = asRecord(plotLike);
    if (!plot) return;

    const plotlyFromNode = parseDirectPlotlyChart(plot.plotly_json ?? plot.plotly);
    if (plotlyFromNode) {
      parsed.push({
        ...plotlyFromNode,
        title:
          layoutTitle ||
          asString(plot.title) ||
          asString(plot.plot_id) ||
          plotlyFromNode.title ||
          "Graph",
      });
      return;
    }

    const series = Array.isArray(plot.series) ? plot.series : [];
    const seriesPoints = series.flatMap((seriesItem) => {
      const entry = asRecord(seriesItem);
      if (!entry) return [];
      const fromPoints = parsePointArray(entry.points);
      if (fromPoints.length > 0) return fromPoints;
      return parseSeriesXYArray(entry);
    });

    const fallbackPoints = parsePointArray(plot.points);
    const points = seriesPoints.length > 0 ? seriesPoints : fallbackPoints;
    if (points.length < 2) return;

    parsed.push({
      title: layoutTitle || asString(plot.title) || asString(plot.name) || "Graph",
      xLabel: asString(plot.x_label) || "x",
      yLabel: asString(plot.y_label) || "y",
      expressionLatex:
        asString(asRecord(plot.recipe)?.expr) ||
        asString(asRecord(series[0])?.expression_latex) ||
        asString(asRecord(series[0])?.expression) ||
        undefined,
      points,
    });
  });

  if (parsed.length > 0) return parsed;

  const directPoints = parsePointArray(obj.points);
  if (directPoints.length >= 2) {
    return [
      {
        title: layoutTitle || asString(obj.title) || "Graph",
        xLabel: asString(obj.xLabel) || "x",
        yLabel: asString(obj.yLabel) || "y",
        points: directPoints,
      },
    ];
  }
  return [];
};

const parseStepsFromObject = (value: unknown): StepRow[] => {
  const obj = asRecord(value);
  if (!obj) return [];

  const solution = asRecord(obj.solution);
  const stepsContainer = solution ?? obj;
  const stepsLike = Array.isArray(stepsContainer.steps) ? stepsContainer.steps : [];
  const directSteps: StepRow[] = [];

  const extractDisplayMath = (text: string): string | undefined => {
    const value = String(text || "");
    const blockMatch = value.match(/\\\[\s*([\s\S]*?)\s*\\\]/);
    if (blockMatch?.[1]) return blockMatch[1].trim();
    const inlineMatch = value.match(/\\\(\s*([\s\S]*?)\s*\\\)/);
    if (inlineMatch?.[1]) return inlineMatch[1].trim();
    return undefined;
  };

  const stripBoilerplate = (text: string): string => {
    let out = String(text || "").trim();
    out = out.replace(
      /^to solve the problem,\s*we need to follow these steps:\s*1\.\s*identify the given equation\.\s*2\.\s*solve the equation step by step\.\s*/i,
      ""
    );
    out = out.replace(/^to solve the problem,\s*we need to follow these steps:\s*/i, "");
    out = out.replace(/^given equation:\s*/i, "");
    if (/given equation:/i.test(out)) {
      const parts = out.split(/given equation:/i);
      out = (parts[parts.length - 1] || "").trim();
    }
    return out.trim();
  };

  const summarizeBoilerplateSteps = (text: string): string | undefined => {
    const value = String(text || "");
    const numbered: string[] = [];
    const matches = value.matchAll(/\b\d+\.\s*([^.\n]+(?:\.[^.\n]+)*)/g);
    for (const match of matches) {
      const part = String(match?.[1] || "").trim();
      if (part) numbered.push(part.replace(/\s+/g, " "));
    }
    if (numbered.length === 0) return undefined;
    return numbered.join(". ");
  };

  const looksLikeAnswerList = (value: string): boolean => {
    const text = String(value || "").trim();
    if (!text) return false;
    if (/^[+-]?\d+(?:\.\d+)?\s*,\s*[+-]?\d+(?:\.\d+)?(?:\s*,\s*[+-]?\d+(?:\.\d+)?)*$/.test(text)) return true;
    if (/^[+-]?\d+\s*\/\s*\d+$/.test(text)) return true;
    return false;
  };

  stepsLike.forEach((step, index) => {
    const entry = asRecord(step);
    if (!entry) return;
    const stepId = Number(entry.step_id);
    const fallbackIndex = Number.isFinite(stepId) && stepId > 0 ? stepId : index + 1;
    const title = asString(entry.title) || `Step ${fallbackIndex}`;
    const rawExplanation = asString(entry.explanation) || "";
    const blocksRaw = Array.isArray(entry.blocks) ? entry.blocks : [];
    const blockTextParts: string[] = [];
    const blockMathParts: string[] = [];
    blocksRaw.forEach((blockLike) => {
      const block = asRecord(blockLike);
      if (!block) return;
      const blockContent = (asString(block.content) || "").trim();
      if (!blockContent) return;
      const blockKind = (asString(block.kind) || "text").toLowerCase();
      if (blockKind === "math") {
        blockMathParts.push(blockContent);
        return;
      }
      blockTextParts.push(blockContent);
    });
    const extractedMath = extractDisplayMath(rawExplanation);
    const cleanedExplanationRaw = stripBoilerplate(rawExplanation);
    const cleanedExplanation = cleanedExplanationRaw
      .replace(/\\\[\s*[\s\S]*?\s*\\\]/g, " ")
      .replace(/\\\(\s*[\s\S]*?\s*\\\)/g, " ")
      .replace(/\s{2,}/g, " ")
      .trim();
    const recoveredExplanation = summarizeBoilerplateSteps(rawExplanation);
    const mathRaw = entry.math ?? entry.math_latex;
    let mathLatex = Array.isArray(mathRaw)
      ? mathRaw.map((item) => asString(item) || "").filter(Boolean).join(" \\\\ ")
      : asString(mathRaw) || undefined;
    if (extractedMath && (!mathLatex || looksLikeAnswerList(mathLatex))) {
      mathLatex = extractedMath;
    }
    const explanationFromBlocks = blockTextParts.join(" ").trim();
    const mathFromBlocks = blockMathParts.join(" \\\\ ").trim();
    const resolvedMath =
      mathFromBlocks ||
      (mathLatex ? mathLatex.trim() : "");
    const resolvedExplanation =
      explanationFromBlocks ||
      cleanedExplanation ||
      recoveredExplanation ||
      undefined;

    directSteps.push({
      title,
      explanation: resolvedExplanation,
      mathLatex: resolvedMath || undefined,
      rulesUsed: asStringArray(entry.rules_used),
      checks: asStringArray(entry.checks),
      notes: asString(entry.notes) || undefined,
    });
  });

  if (directSteps.length > 0) return directSteps;

  const hints = getHintsList(obj);
  if (hints.length > 0) {
    const hintSteps: StepRow[] = hints.map((hint, index) => ({
      title: asString(hint.key) || `Step ${index + 1}`,
      explanation: asString(hint.value) || undefined,
    }));
    if (hintSteps.length > 0) return hintSteps;
  }

  const outputBlocks = Array.isArray(obj.output) ? obj.output : [];
  const mappedFromBlocks: StepRow[] = [];
  outputBlocks.forEach((block, index) => {
    const entry = asRecord(block);
    if (!entry) return;
    const type = (asString(entry.type) || "").toLowerCase();
    if (type !== "worked_step" && type !== "explanation") return;
    mappedFromBlocks.push({
      title: asString(entry.title) || `Step ${index + 1}`,
      explanation: asString(entry.explanation) || asString(entry.text) || undefined,
      mathLatex:
        asString(entry.math_latex) ||
        [asString(entry.before_latex), asString(entry.after_latex)].filter(Boolean).join(" \\Rightarrow "),
    });
  });

  return mappedFromBlocks;
};

const parseTaskResultSteps = (value: unknown): StepRow[] => {
  const obj = asRecord(value);
  if (!obj) return [];
  const results = asRecord(obj.results);
  const taskResults = Array.isArray(results?.task_results) ? results?.task_results : [];
  return taskResults
    .map((taskLike, idx) => {
      const task = asRecord(taskLike);
      if (!task) return null;
      const label = (asString(task.task_label) || "").trim();
      const indexRaw = Number(task.task_index);
      const indexLabel = Number.isFinite(indexRaw) && indexRaw > 0 ? indexRaw : idx + 1;
      const title = label || `Task ${indexLabel}`;
      const explanation = cleanAnswerCandidate(asString(task.result_text) || undefined);
      const mathLatex = cleanAnswerCandidate(asString(task.result_latex) || undefined);
      if (!explanation && !mathLatex) return null;
      return {
        title,
        explanation: explanation || undefined,
        mathLatex: mathLatex || undefined,
      } as StepRow;
    })
    .filter((row): row is StepRow => Boolean(row));
};

const parseResultFromObject = (value: unknown): string | undefined => {
  const obj = asRecord(value);
  if (!obj) return undefined;

  const finalAnswer = asRecord(asRecord(obj.solution)?.final_answer) || asRecord(obj.final_answer);
  if (finalAnswer) {
    const candidate = cleanAnswerCandidate(
      asString(finalAnswer.latex) ||
      asString(finalAnswer.value) ||
      asString(finalAnswer.answer_latex) ||
      asString(finalAnswer.answer_text) ||
      asString(finalAnswer.value_latex) ||
      asString(finalAnswer.value) ||
      undefined,
    );
    if (candidate) return candidate;
  }

  const answer = asRecord(obj.answer);
  if (answer) {
    const candidate = cleanAnswerCandidate(asString(answer.final_latex) || asString(answer.final_text) || undefined);
    if (candidate) return candidate;
  }

  const extractedAnswer = cleanAnswerCandidate(asString(obj.extracted_answer) || undefined);
  if (extractedAnswer) {
    return extractedAnswer;
  }

  const hints = getHintsList(obj);
  for (let i = hints.length - 1; i >= 0; i -= 1) {
    const hintValue = cleanAnswerCandidate(asString(hints[i].value) || undefined);
    if (hintValue) return hintValue;
  }

  return cleanAnswerCandidate(asString(obj.result) || undefined);
};

const parseRecognizedLatexFromObject = (value: unknown): string | undefined => {
  const obj = asRecord(value);
  if (!obj) return undefined;
  const problem = asRecord(obj.problem) || asRecord(obj.question);
  if (problem) {
    return (
      asString(problem.normalized_text) ||
      asString(problem.normalized_latex) ||
      asString(problem.original_text) ||
      undefined
    );
  }
  const hints = getHintsList(obj);
  if (hints.length > 0) {
    const firstHint = asString(hints[0].value);
    if (firstHint && firstHint.trim()) return firstHint.trim();
  }
  return asString(obj.problem_text) || asString(obj.input) || undefined;
};

const parseVerificationChecks = (value: unknown): VerificationCheck[] => {
  const obj = asRecord(value);
  if (!obj) return [];
  const verification = asRecord(obj.verification);
  if (!verification) return [];
  const checks = Array.isArray(verification.checks) ? verification.checks : [];
  const parsed: VerificationCheck[] = [];
  checks.forEach((check, index) => {
    const entry = asRecord(check);
    if (!entry) return;
    const checkId = asString(entry.check_id) || `check_${index + 1}`;
    const verdictRaw = (asString(entry.verdict) || "unknown").toLowerCase();
    const verdict: VerificationCheck["verdict"] =
      verdictRaw === "pass" || verdictRaw === "warn" || verdictRaw === "fail" ? verdictRaw : "unknown";
    const message = asString(entry.message) || "";
    if (!message) return;
    const evidenceMath = asStringArray(entry.evidence_math).join(" \\\\ ");
    const relatedStepIdRaw = Number(entry.related_step_id);
    parsed.push({
      checkId,
      verdict,
      message,
      relatedStepId: Number.isFinite(relatedStepIdRaw) ? relatedStepIdRaw : null,
      evidenceMath: evidenceMath || undefined,
    });
  });
  return parsed;
};

const parseChartPayloadFromPlotly = (value: unknown): ChartPayload[] => {
  const obj = asRecord(value);
  if (!obj) return [];
  const data = Array.isArray(obj.data) ? obj.data : [];
  const layout = asRecord(obj.layout);
  const title =
    asString(layout?.title) ||
    asString(asRecord(layout?.title)?.text) ||
    "Graph";
  const charts: ChartPayload[] = [];
  data.forEach((traceLike, index) => {
    const trace = asRecord(traceLike);
    if (!trace) return;
    const xs = Array.isArray(trace.x) ? trace.x : [];
    const ys = Array.isArray(trace.y) ? trace.y : [];
    const points: ChartPayload["points"] = [];
    const len = Math.min(xs.length, ys.length, 400);
    for (let i = 0; i < len; i += 1) {
      const x = Number(xs[i]);
      const y = Number(ys[i]);
      if (Number.isFinite(x) && Number.isFinite(y)) points.push({ x, y });
    }
    if (points.length >= 2) {
      charts.push({
        title: `${title}${data.length > 1 ? ` (${index + 1})` : ""}`,
        xLabel: asString(asRecord(layout?.xaxis)?.title) || "x",
        yLabel: asString(asRecord(layout?.yaxis)?.title) || "y",
        points,
      });
    }
  });
  return charts;
};

export const parseSolutionDocFromStructured = (value: unknown): MathSolutionPayload | null => {
  const structured = asRecord(value);
  const doc = asRecord(structured?.solution_doc);
  if (!doc) return null;

  const recognized = asRecord(doc.recognized_problem);
  const stepsRaw = Array.isArray(doc.steps) ? doc.steps : [];
  const steps: StepRow[] = stepsRaw
    .map((row) => {
      const step = asRecord(row);
      if (!step) return null;
      const kRaw = Number(step.k);
      const k = Number.isFinite(kRaw) && kRaw > 0 ? kRaw : undefined;
      const title = asString(step.title) || (k ? `Step ${k}` : "Step");
      const body = asString(step.body_markdown) || "";
      return {
        k,
        title,
        bodyMarkdown: body || undefined,
        explanation: body || undefined,
      } as StepRow;
    })
    .filter((row): row is StepRow => Boolean(row));

  const finalAnswer = asRecord(doc.final_answer);
  const verification = Array.isArray(doc.verification) ? doc.verification : [];
  const verificationChecks: VerificationCheck[] = [];
  verification.forEach((v, idx) => {
    const text = asString(v);
    if (!text) return;
    verificationChecks.push({
      checkId: `check_${idx + 1}`,
      verdict: "unknown",
      message: text,
    });
  });

  const plotsRaw = Array.isArray(doc.plots) ? doc.plots : [];
  const plots = plotsRaw.flatMap((entry) => parseChartPayloadFromPlotly(asRecord(entry)?.plotly));
  const autocorrect = asRecord(doc.autocorrect);
  const parseStatusRaw = asString(doc.parse_status);
  const parseStatus =
    parseStatusRaw === "ok" || parseStatusRaw === "partial" || parseStatusRaw === "failed"
      ? parseStatusRaw
      : undefined;

  return {
    recognizedLatex: asString(recognized?.latex) || asString(recognized?.text) || undefined,
    domainConstraints: asStringArray(doc.domain_constraints),
    steps,
    result: cleanAnswerCandidate(asString(finalAnswer?.latex) || asString(finalAnswer?.text) || undefined),
    plots,
    verificationChecks,
    autocorrectApplied: Boolean(autocorrect?.applied),
    parseStatus,
  };
};

const parseFinalAnswerFromObject = (value: unknown): MathSolutionPayload["finalAnswer"] => {
  const asStr = asString(value);
  if (asStr) {
    return {
      answer_text: "",
      answer_latex: asStr,
      values: [],
    };
  }

  const obj = asRecord(value);
  if (!obj) return undefined;

  const answerText = asString(obj.answer_text) || "";
  const answerLatex = asString(obj.answer_latex) || "";

  const valuesRaw = Array.isArray(obj.values) ? obj.values : [];
  const values = valuesRaw
    .map((v) => {
      const vObj = asRecord(v);
      if (!vObj) return null;
      const legacyLabel = asString(vObj.label);
      const key = asString(vObj.key) || undefined;
      const label = (legacyLabel || key || "Value").trim();
      const legacyValue = vObj.value as string | number | boolean | Record<string, unknown> | null;
      const valueFromV2 =
        (vObj.number as string | number | boolean | Record<string, unknown> | null) ??
        (vObj.text as string | number | boolean | Record<string, unknown> | null) ??
        null;
      return {
        key,
        label,
        value: legacyValue ?? valueFromV2,
        value_latex: asString(vObj.value_latex) || asString(vObj.latex) || undefined,
        unit: asString(vObj.unit) || undefined,
      };
    })
    .filter((v): v is NonNullable<typeof v> => v !== null);

  if (!answerText && !answerLatex && values.length === 0) return undefined;

  return {
    answer_text: answerText,
    answer_latex: answerLatex,
    values,
  };
};

const parseSectionedShortPayload = (
  value: unknown,
  context?: { questionText?: string; originalProblem?: string }
): MathSolutionPayload | null => {
  const obj = asRecord(value);
  if (!obj) return null;
  const sectionsRaw = Array.isArray(obj.sections) ? obj.sections : [];
  if (sectionsRaw.length === 0) return null;

  const shortSections: ShortSection[] = [];
  const steps: StepRow[] = [];

  sectionsRaw.forEach((sectionLike) => {
    const section = asRecord(sectionLike);
    if (!section) return;

    const sectionHeading = asString(section.heading) || asString(section.label) || "Section";
    const sectionLabel = asString(section.label) || sectionHeading.replace(/[()]/g, "").trim() || "section";
    const stepRows = Array.isArray(section.steps) ? section.steps : [];
    const parsedSectionSteps: ShortSection["steps"] = [];

    stepRows.forEach((stepLike, idx) => {
      const step = asRecord(stepLike);
      if (!step) return;

      const stepIndexRaw = Number(step.index);
      const stepIndex = Number.isFinite(stepIndexRaw) && stepIndexRaw > 0 ? stepIndexRaw : idx + 1;

      const blocksRaw = Array.isArray(step.blocks) ? step.blocks : [];
      const parsedBlocks = blocksRaw
        .map((blockLike) => {
          const block = asRecord(blockLike);
          if (!block) return null;
          const kind = (asString(block.kind) || "text").trim();
          const content = (asString(block.content) || "").trim();
          if (!content) return null;
          return { kind, content };
        })
        .filter((block): block is { kind: string; content: string } => Boolean(block));

      const stepKind = (asString(step.kind) || "work").trim().toLowerCase();
      const stepRaw = asString(step.raw) || undefined;

      parsedSectionSteps.push({
        index: stepIndex,
        kind: stepKind || "work",
        raw: stepRaw,
        blocks: parsedBlocks,
      });

      const textParts = parsedBlocks
        .filter((b) => b.kind.toLowerCase() !== "math")
        .map((b) => b.content);
      const mathParts = parsedBlocks
        .filter((b) => b.kind.toLowerCase() === "math")
        .map((b) => b.content);
      const fallbackRaw = (stepRaw || "").trim();

      steps.push({
        title: `${sectionHeading} Step ${stepIndex}`,
        explanation: textParts.length > 0 ? textParts.join(" ").trim() : fallbackRaw || undefined,
        mathLatex: mathParts.length > 0 ? mathParts.join(" \\\\ ").trim() : undefined,
      });
    });

    shortSections.push({
      label: sectionLabel,
      heading: sectionHeading,
      steps: parsedSectionSteps,
      finalAnswer: asString(section.final_answer) || undefined,
      incomplete: Boolean(section.incomplete),
    });
  });

  const result = cleanAnswerCandidate(asString(obj.global_final_answer) || undefined);
  const recognized =
    context?.questionText ||
    context?.originalProblem ||
    asString(asRecord(obj.question)?.text) ||
    asString(asRecord(obj.problem)?.original_text) ||
    undefined;

  return {
    steps,
    shortSections,
    result,
    recognizedLatex: recognized,
    finalAnswer: result
      ? {
          answer_text: result,
          answer_latex: result,
          values: [],
        }
      : undefined,
    originalProblem: context?.originalProblem || asString(asRecord(obj.problem)?.original_text) || recognized || undefined,
    normalizedProblem: recognized,
  };
};

const parseMathSolutionFromObject = (value: unknown): MathSolutionPayload | null => {
  const obj = asRecord(value);
  if (!obj) return null;

  // Short-tier custom extractor shape: {sections, global_final_answer, ...}
  const directSectioned = parseSectionedShortPayload(obj);
  if (directSectioned) return directSectioned;

  // Short-tier wrapper may keep parser output under raw_user_extraction.
  const rawUserExtraction = asRecord(obj.raw_user_extraction);
  if (rawUserExtraction) {
    const nestedSectioned = parseSectionedShortPayload(rawUserExtraction, {
      questionText:
        asString(asRecord(obj.problem)?.original_text) ||
        asString(asRecord(obj.question)?.text) ||
        undefined,
      originalProblem: asString(asRecord(obj.problem)?.original_text) || undefined,
    });
    if (nestedSectioned) return nestedSectioned;
  }

  // New solve payload shape stores per-question outputs under `items[]`.
  // Use the first non-refusal item as the primary canvas solution.
  const rawItems = Array.isArray(obj.items) ? obj.items : [];
  const parsedItems = rawItems
    .map((item) => asRecord(item))
    .filter((item): item is Record<string, unknown> => Boolean(item));
  if (parsedItems.length > 0) {
    const primaryItem =
      parsedItems.find((item) => asRecord(item.refusal)?.is_refusal !== true) || parsedItems[0];
    const parsedPrimary = parseMathSolutionFromObject(primaryItem);
    if (parsedPrimary) {
      const rootOriginal =
        asString(asRecord(obj.problem)?.original_text) ||
        asString(asRecord(obj.question)?.original_text) ||
        asString(asRecord(obj.question)?.text) ||
        undefined;
      const rootNormalized =
        asString(asRecord(obj.problem)?.normalized_text) ||
        asString(asRecord(obj.question)?.normalized_text) ||
        undefined;
      return {
        ...parsedPrimary,
        originalProblem: parsedPrimary.originalProblem || rootOriginal,
        normalizedProblem: parsedPrimary.normalizedProblem || rootNormalized,
      };
    }
  }

  const layoutTitle = parseLayoutTitleFromObject(obj);
  const steps = parseStepsFromObject(obj);
  const taskResultSteps = parseTaskResultSteps(obj);
  const combinedSteps =
    steps.length > 0
      ? [...steps, ...taskResultSteps]
      : taskResultSteps;
  const result = parseResultFromObject(obj);
  const recognizedLatex = parseRecognizedLatexFromObject(obj);
  const plots = parsePlotFromObject(obj);
  const verificationChecks = parseVerificationChecks(obj);
  const finalAnswer = parseFinalAnswerFromObject(obj.final_answer ?? asRecord(obj.solution)?.final_answer);
  const plotPayload = asRecord(obj.plot) || undefined;
  const pythonCode =
    asString(obj.python_code) ||
    asString(plotPayload?.python_code) ||
    undefined;

  if (
    !recognizedLatex &&
    combinedSteps.length === 0 &&
    !result &&
    plots.length === 0 &&
    verificationChecks.length === 0 &&
    !finalAnswer &&
    !plotPayload &&
    !pythonCode
  ) {
    return null;
  }

  const questionText = compactQuestionText(asString(obj.question_text) || undefined);
  const questionSummary = asString(obj.question_summary) || undefined;
  return {
    layoutTitle,
    recognizedLatex: recognizedLatex || questionSummary || questionText,
    steps: combinedSteps,
    result,
    finalAnswer,
    plots,
    plotPayload,
    pythonCode,
    verificationChecks,
    assumptions: asStringArray(obj.assumptions),
    originalProblem:
      questionSummary ||
      questionText ||
      asString(asRecord(obj.problem)?.original_text) ||
      asString(asRecord(obj.problem)?.text) ||
      undefined,
    normalizedProblem:
      asString(asRecord(obj.problem)?.normalized_text) ||
      questionSummary ||
      undefined,
    confidence: Number(asRecord(obj.quality)?.confidence) || Number(asRecord(obj.accuracy)?.confidence) || undefined,
    commonMistakes: asStringArray(asRecord(obj.quality)?.common_mistakes),
  };
};

const extractBalancedJson = (text: string): Array<{ json: string; start: number; end: number }> => {
  const matches: Array<{ json: string; start: number; end: number }> = [];
  let depth = 0;
  let start = -1;
  let inString = false;
  let escaped = false;

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (ch === "\\") {
        escaped = true;
      } else if (ch === "\"") {
        inString = false;
      }
      continue;
    }

    if (ch === "\"") {
      inString = true;
      continue;
    }

    if (ch === "{") {
      if (depth === 0) start = i;
      depth += 1;
      continue;
    }

    if (ch === "}") {
      if (depth <= 0) continue;
      depth -= 1;
      if (depth === 0 && start >= 0) {
        matches.push({ json: text.slice(start, i + 1), start, end: i + 1 });
        if (matches.length >= 4) break;
      }
    }
  }

  return matches;
};

const safeParseJson = (raw: string): Record<string, unknown> | null => {
  if (!raw || raw.length > JSON_SIZE_LIMIT) return null;
  try {
    const parsed = JSON.parse(raw) as unknown;
    return asRecord(parsed);
  } catch {
    return null;
  }
};

const detectLatexFromText = (text: string): string | undefined => {
  const display = text.match(/\$\$([\s\S]+?)\$\$/);
  if (display?.[1]) return display[1].trim();
  const bracket = text.match(/\\\[((?:.|\n)+?)\\\]/);
  if (bracket?.[1]) return bracket[1].trim();
  const inline = text.match(/\$([^$\n]+)\$/);
  if (inline?.[1]) return inline[1].trim();

  const candidate = text
    .split("\n")
    .map((line) => line.trim())
    .find((line) => /[=+\-*/^_()]/.test(line) && line.length <= 160);
  return candidate || undefined;
};

const normalizeStepLine = (line: string): string =>
  line
    .replace(/[\u200e\u200f]/g, "")
    .replace(/^#{1,6}\s*/, "")
    .replace(/^>\s*/, "")
    .replace(/\*\*/g, "")
    .replace(/__/g, "")
    .replace(/`([^`]+)`/g, "$1")
    .trim();

const isDelimiterOnlyLine = (line: string): boolean => /^\\[\[\]\(\)]$/.test(line.trim());

const looksLikeMathLine = (line: string): boolean => {
  const trimmed = line.trim();
  if (!trimmed) return false;
  if (isDelimiterOnlyLine(trimmed)) return false;

  if (/\\(boxed|frac|sqrt|int|sum|lim|sin|cos|tan|log|ln|pi|theta|left|right|begin|end)\b/i.test(trimmed)) {
    return true;
  }

  const words = trimmed.split(/\s+/).filter(Boolean);
  const wordCount = words.length;
  const alphaCount = (trimmed.match(/[A-Za-z]/g) || []).length;
  const nonAlphaCount = trimmed.length - alphaCount;
  const startsLikeSentence = /^[A-Z]/.test(trimmed);
  const hasEquation = /[=<>]/.test(trimmed);
  const hasMathSymbols = /[+\-*/^_{}]/.test(trimmed);
  if (startsLikeSentence && wordCount >= 8) return false;
  if ((hasEquation || hasMathSymbols) && wordCount <= 6) return true;
  if ((hasEquation || hasMathSymbols) && nonAlphaCount > alphaCount * 1.35) return true;

  return false;
};

const cleanAnswerCandidate = (value: string | undefined): string | undefined => {
  const trimmed = (value || "").trim();
  if (!trimmed) return undefined;
  const cleaned = trimmed
    .replace(/^\*{1,3}\s*/, "")
    .replace(/\s*\*{1,3}$/, "")
    .replace(/^\(?\d+\)?[.)]\s*/, "")
    .replace(/\s{2,}/g, " ")
    .trim();
  if (!cleaned) return undefined;
  if (/^(?:n\/?a|none|null|not provided|unknown|-+)$/i.test(cleaned)) return undefined;
  if (/^(step|verification|domain|check|plotly)\b/i.test(cleaned)) return undefined;
  if (/^sub(?:stitution)?\.?$/i.test(cleaned)) return undefined;
  if (/^\(?\d+\)?[.)-]?\s*[A-Za-z]{1,20}$/.test(cleaned)) return undefined;
  return cleaned;
};

const compactQuestionText = (value: string | undefined): string | undefined => {
  const raw = (value || "").trim();
  if (!raw) return undefined;
  const normalized = raw.replace(/\r\n/g, "\n");
  const taskStart = normalized.search(/\n\s*tasks?\s*:/i);
  const base = taskStart >= 0 ? normalized.slice(0, taskStart).trim() : normalized;
  if (!base) return undefined;
  return base.replace(/^q\d+\s*:\s*/i, "").trim();
};

const isPlaceholderLine = (value: string): boolean =>
  /^(?:none|n\/?a|null|not provided|unknown|-+)$/i.test((value || "").trim());

const detectStepsFromText = (text: string): StepRow[] => {
  const lines = text
    .split("\n")
    .map((line) => normalizeStepLine(line))
    .filter(Boolean);

  const stepPattern = /^(?:step\s*(\d+)|\(?(\d+)\)?)[\s:.)\-–—]*\s*(.+)?$/i;
  const steps: StepRow[] = [];
  let current: { title: string; explanationParts: string[]; mathParts: string[] } | null = null;

  const pushCurrent = () => {
    if (!current) return;
    const explanation = current.explanationParts.join(" ").trim();
    const mathLatex = current.mathParts.join(" \\\\ ").trim();
    steps.push({
      title: current.title,
      explanation: explanation || undefined,
      mathLatex: mathLatex || undefined,
    });
    current = null;
  };

  lines.forEach((line, index) => {
    if (/^(?:final answer|answer|therefore|so)\b/i.test(line)) {
      pushCurrent();
      return;
    }
    const match = line.match(stepPattern);
    if (match) {
      pushCurrent();
      const stepNumber = match[1] || match[2] || String(steps.length + 1);
      const initialText = (match[3] || "").trim();
      current = {
        title: `Step ${stepNumber}`,
        explanationParts: initialText ? [initialText] : [],
        mathParts: [],
      };
      return;
    }

    if (current) {
      const bullet = line.replace(/^[-*]\s+/, "").trim();
      if (/^[-*]\s+/.test(line)) {
        if (bullet && !isPlaceholderLine(bullet)) current.explanationParts.push(bullet);
        return;
      }
      if (isDelimiterOnlyLine(line)) {
        return;
      }
      if (looksLikeMathLine(line)) {
        current.mathParts.push(line);
        return;
      }
      current.explanationParts.push(line);
      return;
    }

    if (/^\(?\d+\)?[.)\-–—]\s+/.test(line)) {
      const textLine = line.replace(/^\(?\d+\)?[.)\-–—]\s+/, "").trim();
      if (textLine && !isPlaceholderLine(textLine)) {
        steps.push({
          title: `Step ${steps.length + 1}`,
          explanation: textLine,
        });
      }
      return;
    }

    if (/^[-*]\s+/.test(line)) {
      const bullet = line.replace(/^[-*]\s+/, "").trim();
      if (bullet && !isPlaceholderLine(bullet)) {
        steps.push({
          title: `Step ${steps.length + 1}`,
          explanation: bullet,
        });
      }
      return;
    }

    if (index < 8 && /(?:simplify|solve|expand|factor|substitute|evaluate|isolate|rearrange)/i.test(line)) {
      steps.push({
        title: `Step ${steps.length + 1}`,
        explanation: line,
      });
    }
  });

  pushCurrent();
  return steps.slice(0, 32);
};

const detectResultFromText = (text: string): string | undefined => {
  const lines = text.split("\n");
  for (const line of lines) {
    const trimmed = line.trim().replace(/\*\*/g, "");
    if (!trimmed) continue;
    const match = trimmed.match(
      /^(?:final answer(?: value| latex)?|final_answer(?:\s*\(value\)|\s*value)?|answer|therefore|so)\s*[:=-]\s*(.+)$/i
    );
    const candidate = cleanAnswerCandidate(match?.[1]);
    if (candidate) return candidate;
  }
  const boxedMatches = [...text.matchAll(/\\boxed\{([^}]+)\}/g)];
  for (let i = boxedMatches.length - 1; i >= 0; i -= 1) {
    const candidate = cleanAnswerCandidate(boxedMatches[i][1]);
    if (candidate) return candidate;
  }
  const blocks = [...text.matchAll(/\\\[((?:.|\n)*?)\\\]/g)];
  for (let i = blocks.length - 1; i >= 0; i -= 1) {
    const candidate = cleanAnswerCandidate(blocks[i][1]);
    if (candidate && /[=<>]|\\(frac|sqrt|pi|theta|boxed)/i.test(candidate)) {
      return candidate;
    }
  }
  const equationLines = text.match(/^\s*([^\n]{1,260}[=<>][^\n]{1,260})\s*$/gm) || [];
  for (let i = equationLines.length - 1; i >= 0; i -= 1) {
    const candidate = cleanAnswerCandidate(equationLines[i]);
    if (candidate) return candidate;
  }
  const thereforeInline = text.match(/therefore[,:\s]+(.+)$/im);
  return cleanAnswerCandidate(thereforeInline?.[1]);
};

const detectPlotFromText = (text: string): ChartPayload | null => {
  const pointRegex = /\((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)/g;
  const points: ChartPayload["points"] = [];
  let match: RegExpExecArray | null = pointRegex.exec(text);
  while (match) {
    points.push({ x: Number(match[1]), y: Number(match[2]) });
    if (points.length >= 50) break;
    match = pointRegex.exec(text);
  }
  if (points.length < 2) return null;
  return {
    title: "Parsed points",
    xLabel: "x",
    yLabel: "y",
    points,
  };
};

const parseNumberArray = (raw: string): number[] =>
  raw
    .split(",")
    .map((item) => Number(item.trim()))
    .filter((value) => Number.isFinite(value));

const detectPlotlyArraysFromText = (text: string): ChartPayload | null => {
  const blockMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const source = (blockMatch?.[1] || text).replace(/[\r\n]+/g, " ");

  const xMatch = source.match(/["']?\s*x\s*["']?\s*:\s*\[([^\]]+)\]/i);
  const yMatch = source.match(/["']?\s*y\s*["']?\s*:\s*\[([^\]]+)\]/i);
  if (!xMatch?.[1] || !yMatch?.[1]) return null;

  const xs = parseNumberArray(xMatch[1]);
  const ys = parseNumberArray(yMatch[1]);
  const length = Math.min(xs.length, ys.length);
  if (length < 2) return null;

  const titleMatch = source.match(/["']?\s*title\s*["']?\s*:\s*["']([^"']+)["']/i);
  return {
    title: (titleMatch?.[1] || "Graph").trim(),
    xLabel: "x",
    yLabel: "y",
    points: Array.from({ length }).map((_, i) => ({ x: xs[i], y: ys[i] })),
  };
};

const extractSolutionFromText = (text: string): {
  solution: MathSolutionPayload | null;
  remainingText: string;
} => {
  let remainingText = text;
  let parsedSolution: MathSolutionPayload | null = null;

  const fencedRegex = /```(?:json)?\s*([\s\S]*?)```/gi;
  let fencedMatch = fencedRegex.exec(text);
  while (fencedMatch) {
    const parsed = safeParseJson(fencedMatch[1] || "");
    const candidate = parseMathSolutionFromObject(parsed);
    if (candidate) {
      parsedSolution = candidate;
      remainingText = remainingText.replace(fencedMatch[0], "").trim();
      break;
    }
    fencedMatch = fencedRegex.exec(text);
  }

  if (!parsedSolution) {
    const balanced = extractBalancedJson(text);
    for (const entry of balanced) {
      const parsed = safeParseJson(entry.json);
      const candidate = parseMathSolutionFromObject(parsed);
      if (candidate) {
        parsedSolution = candidate;
        remainingText = `${text.slice(0, entry.start)} ${text.slice(entry.end)}`.trim();
        break;
      }
    }
  }

  if (!parsedSolution) {
    const textSteps = detectStepsFromText(text);
    const textResult = detectResultFromText(text);
    const recognizedLatex = detectLatexFromText(text);
    const textPlot = detectPlotlyArraysFromText(text) || detectPlotFromText(text);
    if (textSteps.length > 0 || textResult || recognizedLatex || textPlot) {
      parsedSolution = {
        recognizedLatex,
        steps: textSteps,
        result: textResult,
        plots: textPlot ? [textPlot] : [],
      };
    }
  }

  return {
    solution: parsedSolution,
    remainingText,
  };
};

export const normalizeAssistantMessage = (
  message: SessionMessage,
  index: number
): NormalizedChatMessage => {
  const role = message.role === "assistant" ? "assistant" : "user";
  const base: NormalizedChatMessage = {
    id: String(message.id ?? `${role}-${index}`),
    role,
    createdAt: message.created_at,
    modelUsed: message.model_used,
    items: [],
  };

  const contentText =
    asString(message.display_markdown) ||
    asString(message.rendered_content) ||
    asString(asRecord(message.structured_data)?.display_markdown) ||
    asString(asRecord(message.structured_data)?.rendered_content) ||
    asString(message.content) ||
    "";
  if (role === "user") {
    base.items.push({ type: "text", text: contentText || "(empty message)" });
    return base;
  }

  const extractedFromContent = contentText.trim() ? extractSolutionFromText(contentText) : { solution: null, remainingText: contentText };
  const solutionDocPayload = parseSolutionDocFromStructured(message.structured_data);
  const structuredSolution = parseMathSolutionFromObject(message.structured_data);
  const allowFallbackFromContent = solutionDocPayload ? solutionDocPayload.parseStatus !== "ok" : true;
  const mergedSolution = solutionDocPayload
    ? {
      ...solutionDocPayload,
      recognizedLatex:
        solutionDocPayload.recognizedLatex ||
        (allowFallbackFromContent ? extractedFromContent.solution?.recognizedLatex : undefined),
      steps:
        solutionDocPayload.steps.length > 0
          ? solutionDocPayload.steps
          : (allowFallbackFromContent ? extractedFromContent.solution?.steps || [] : []),
      result:
        cleanAnswerCandidate(solutionDocPayload.result) ||
        (allowFallbackFromContent ? cleanAnswerCandidate(extractedFromContent.solution?.result) : undefined),
      verificationChecks:
        (solutionDocPayload.verificationChecks?.length || 0) > 0
          ? solutionDocPayload.verificationChecks
          : (allowFallbackFromContent ? extractedFromContent.solution?.verificationChecks || [] : []),
      plots:
        (solutionDocPayload.plots?.length || 0) > 0
          ? solutionDocPayload.plots
          : (allowFallbackFromContent ? extractedFromContent.solution?.plots || [] : []),
    }
    : structuredSolution
      ? {
        ...structuredSolution,
        recognizedLatex: structuredSolution.recognizedLatex || extractedFromContent.solution?.recognizedLatex,
        steps:
          structuredSolution.steps.length > 0
            ? structuredSolution.steps
            : (extractedFromContent.solution?.steps || []),
        result:
          cleanAnswerCandidate(structuredSolution.result) ||
          cleanAnswerCandidate(extractedFromContent.solution?.result),
        verificationChecks:
          (structuredSolution.verificationChecks?.length || 0) > 0
            ? structuredSolution.verificationChecks
            : (extractedFromContent.solution?.verificationChecks || []),
        plots:
          (structuredSolution.plots?.length || 0) > 0
            ? structuredSolution.plots
            : (extractedFromContent.solution?.plots || []),
      }
      : extractedFromContent.solution;

  if (mergedSolution) {
    base.items.push({ type: "math_solution", payload: mergedSolution });
    mergedSolution.plots?.forEach((plot) => {
      base.items.push({ type: "chart", payload: plot });
    });
    const hasMeaningfulSolution =
      (mergedSolution.steps?.length || 0) > 0 ||
      Boolean(cleanAnswerCandidate(mergedSolution.result)) ||
      (mergedSolution.plots?.length || 0) > 0 ||
      Boolean(mergedSolution.plotPayload) ||
      Boolean((mergedSolution.pythonCode || "").trim()) ||
      (mergedSolution.verificationChecks?.length || 0) > 0;
    if (!hasMeaningfulSolution && contentText.trim()) {
      base.items.push({ type: "text", text: contentText.trim() });
    }
  }

  const explicitPlotPayloads = [
    ...parsePlotFromObject(message.chart),
    ...parsePlotFromObject(message.plot),
  ];
  explicitPlotPayloads.forEach((plot) => {
    base.items.push({ type: "chart", payload: plot });
  });

  if (contentText.trim() && !mergedSolution) {
    const remaining = extractedFromContent.remainingText.trim();
    if (remaining) {
      base.items.push({ type: "text", text: remaining });
    }
  }

  if (base.items.length === 0) {
    base.items.push({
      type: "error",
      message: "Message format is unsupported. Showing fallback.",
    });
  }

  return base;
};

export const normalizeSessionMessages = (messages: SessionMessage[]): NormalizedChatMessage[] =>
  messages.map((message, index) => normalizeAssistantMessage(message, index));

export const extractPrimarySolution = (
  messages: NormalizedChatMessage[]
): MathSolutionPayload | null => {
  const assistantMessages = messages.filter((message) => message.role === "assistant");
  for (let i = 0; i < assistantMessages.length; i += 1) {
    const match = assistantMessages[i].items.find((item) => item.type === "math_solution");
    if (match && match.type === "math_solution") return match.payload;
  }
  return null;
};

export interface BatchSolutionItem {
  questionId: string;
  questionText?: string;
  solution: MathSolutionPayload;
}

const parseQuestionOrder = (questionId: string): { group: number; index: number; raw: string } => {
  const trimmed = (questionId || "").trim();
  const simpleQ = trimmed.match(/^q(\d+)$/i);
  if (simpleQ) return { group: 0, index: Number(simpleQ[1]), raw: trimmed.toLowerCase() };

  const trailingDigits = trimmed.match(/(\d+)(?!.*\d)/);
  if (trailingDigits) return { group: 1, index: Number(trailingDigits[1]), raw: trimmed.toLowerCase() };

  return { group: 2, index: Number.MAX_SAFE_INTEGER, raw: trimmed.toLowerCase() };
};

const sortBatchQuestionIds = (left: string, right: string): number => {
  const l = parseQuestionOrder(left);
  const r = parseQuestionOrder(right);
  if (l.group !== r.group) return l.group - r.group;
  if (l.index !== r.index) return l.index - r.index;
  return l.raw.localeCompare(r.raw);
};

const parseQuestionTextMap = (messages: SessionMessage[]): Record<string, string> => {
  const out: Record<string, string> = {};
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const msg = messages[i];
    if (msg.role !== "user") continue;
    const raw = asString(msg.content) || "";
    if (!raw.trim()) continue;

    const lines = raw.split("\n");
    lines.forEach((line) => {
      const match = line.match(/^\s*-\s*\(([^)]+)\)\s*(.+)\s*$/);
      if (!match) return;
      const qid = (match[1] || "").trim();
      const text = (match[2] || "").trim();
      if (qid && text && !out[qid]) {
        out[qid] = text;
      }
    });

    if (Object.keys(out).length > 0) return out;
  }
  return out;
};

export const extractBatchSolutionsFromSessionMessages = (
  messages: SessionMessage[]
): BatchSolutionItem[] => {
  if (!Array.isArray(messages) || messages.length === 0) return [];
  const questionTextMap = parseQuestionTextMap(messages);

  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const msg = messages[i];
    if (msg.role !== "assistant") continue;
    const structured = asRecord(msg.structured_data);
    if (!structured) continue;

    const mode = asString(structured.mode) || "";
    const solutionsRaw = Array.isArray(structured.solutions) ? structured.solutions : [];
    const itemsRaw = Array.isArray(structured.items) ? structured.items : [];
    const rawUserExtraction = asRecord(structured.raw_user_extraction);
    const tierRequested = asString(structured.tier_requested) || asString(asRecord(structured.solve_meta)?.tier_requested) || "";
    const tierEffective = asString(structured.tier_effective) || asString(asRecord(structured.solve_meta)?.tier_effective) || "";
    const looksShortTier = /SHORT/i.test(tierRequested) || /SHORT/i.test(tierEffective);

    // Prefer full short-tier parser output (sections->steps->blocks) when available.
    if ((looksShortTier || rawUserExtraction) && rawUserExtraction) {
      const questionText =
        asString(asRecord(structured.problem)?.original_text) ||
        asString(asRecord(structured.question)?.text) ||
        questionTextMap.q1;
      const parsedShort = parseMathSolutionFromObject({
        ...structured,
        question: asRecord(structured.question) || { text: questionText },
        problem: asRecord(structured.problem) || { original_text: questionText || "" },
        sections: rawUserExtraction.sections,
        global_final_answer: rawUserExtraction.global_final_answer,
      });
      if (parsedShort) {
        return [
          {
            questionId: "q1",
            questionText,
            solution: parsedShort,
          },
        ];
      }
    }

    if (mode !== "batch_text_solve" && solutionsRaw.length === 0 && itemsRaw.length === 0) continue;
    if (solutionsRaw.length === 0) {
      const shortDirect = parseMathSolutionFromObject(structured);
      if (shortDirect) {
        return [
          {
            questionId: "q1",
            questionText:
              asString(asRecord(structured.problem)?.original_text) ||
              asString(asRecord(structured.question)?.text) ||
              questionTextMap.q1,
            solution: shortDirect,
          },
        ];
      }
      return [];
    }

    const parsed = solutionsRaw
      .map((entry) => {
        const solutionObj = asRecord(entry);
        if (!solutionObj) return null;
        const questionId = (asString(solutionObj.question_id) || "").trim();
        if (!questionId) return null;

        const payload = parseMathSolutionFromObject(solutionObj);
        if (!payload) return null;
        return {
          questionId,
          questionText: questionTextMap[questionId],
          solution: payload,
        } as BatchSolutionItem;
      })
      .filter((entry): entry is BatchSolutionItem => Boolean(entry))
      .sort((left, right) => sortBatchQuestionIds(left.questionId, right.questionId));

    if (parsed.length > 0) return parsed;
  }
  return [];
};

export const buildSuggestionPrompts = (steps: string[]): string[] => {
  const base = ["Simplify Eq", "Plot Graph", "Check Steps"];
  const extras = steps
    .filter(Boolean)
    .slice(0, 2)
    .map((step) => `Explain: ${step}`);
  return [...base, ...extras];
};

export const flattenTextItems = (message: NormalizedChatMessage): string =>
  message.items
    .filter((item) => item.type === "text")
    .map((item) => (item.type === "text" ? item.text : ""))
    .join("\n")
    .trim();

export const collectReasonableContext = (messages: NormalizedChatMessage[]): string[] => {
  const lines: string[] = [];
  messages.forEach((message) => {
    if (message.role !== "assistant") return;
    const snippets = message.items
      .filter((item) => item.type === "text")
      .map((item) => (item.type === "text" ? item.text : ""))
      .filter(Boolean);
    lines.push(...snippets);
  });
  return lines.slice(-3);
};

export const sanitizePromptContext = (value: string): string =>
  value.replace(/\s+/g, " ").trim().slice(0, 500);

export const parseStepTitles = (steps: StepRow[]): string[] =>
  steps.map((step) => step.title).filter(Boolean);

export const collectValidationErrors = (message: SessionMessage): string[] => {
  const structured = message.structured_data;
  if (!structured) return [];
  return asStringArray(asRecord(structured)?.validation_errors);
};
