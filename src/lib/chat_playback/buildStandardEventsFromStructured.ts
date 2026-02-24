import { StandardRenderEvent } from "@/lib/chat_playback/types";

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" ? (value as Record<string, unknown>) : null;

const asString = (value: unknown): string =>
  typeof value === "string" ? value : value === null || value === undefined ? "" : String(value);

const isNonEmptyString = (value: unknown): value is string => typeof value === "string" && value.trim().length > 0;

const hashToSeed = (value: string): number => {
  let hash = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
};

const mulberry32 = (seed: number) => {
  let t = seed >>> 0;
  return () => {
    t += 0x6d2b79f5;
    let x = Math.imul(t ^ (t >>> 15), 1 | t);
    x ^= x + Math.imul(x ^ (x >>> 7), 61 | x);
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
};

const chunkText = (text: string, minSize: number, maxSize: number, rand: () => number): string[] => {
  const clean = String(text || "");
  if (!clean) return [];
  const chunks: string[] = [];
  let cursor = 0;
  while (cursor < clean.length) {
    const size = Math.max(minSize, Math.min(maxSize, Math.floor(minSize + rand() * (maxSize - minSize + 1))));
    chunks.push(clean.slice(cursor, cursor + size));
    cursor += size;
  }
  return chunks;
};

export function buildStandardEventsFromStructuredData(
  structured: Record<string, unknown> | null | undefined,
  attemptId: string
): StandardRenderEvent[] {
  const root = asRecord(structured) || {};
  const itemsRaw = Array.isArray(root.items) ? root.items : [];
  const item = asRecord(itemsRaw[0]) || {};
  const seedSource = isNonEmptyString(attemptId) ? attemptId : "standard-playback";
  const rand = mulberry32(hashToSeed(seedSource));
  const events: StandardRenderEvent[] = [];
  let t = 0;
  let i = 0;

  const push = (type: StandardRenderEvent["type"], payload: Record<string, unknown>, dt = 0) => {
    t += Math.max(0, dt);
    i += 1;
    events.push({
      id: `std_evt_${String(i).padStart(5, "0")}`,
      at_ms: t,
      type,
      payload,
    });
  };

  push("MESSAGE_START", {});
  push("QUESTION_START", {}, 40);

  const questionSummary = asString(item.question_summary).trim();
  if (questionSummary) {
    for (const chunk of chunkText(questionSummary, 14, 22, rand)) {
      push("QUESTION_APPEND_SUMMARY", { chunk }, 18 + Math.floor(rand() * 16));
    }
  }

  const questionText = asString(item.question_text).trim();
  if (questionText) {
    for (const chunk of chunkText(questionText, 12, 20, rand)) {
      push("QUESTION_APPEND_TEXT", { chunk }, 12 + Math.floor(rand() * 14));
    }
  }

  const tasksRaw = Array.isArray(item.tasks) ? item.tasks : [];
  const tasks = tasksRaw
    .map((entry) => asRecord(entry))
    .filter((entry): entry is Record<string, unknown> => Boolean(entry))
    .map((entry, idx) => ({
      task_index: Number(entry.task_index ?? idx + 1),
      task_label: asString(entry.task_label).trim() || `Task ${idx + 1}`,
    }));
  if (tasks.length > 0) {
    push("TASKS_SET", { tasks }, 70);
  }

  const stepsRaw = Array.isArray(item.steps) ? item.steps : [];
  for (const stepEntry of stepsRaw) {
    const step = asRecord(stepEntry) || {};
    const stepIndex = Number(step.index || 0);
    const stepTitle = asString(step.title).trim() || `Step ${stepIndex || 1}`;
    push("STEP_START", { step_index: stepIndex, title: stepTitle }, 140 + Math.floor(rand() * 80));

    const blocks = Array.isArray(step.blocks) ? step.blocks : [];
    for (let blockIndex = 0; blockIndex < blocks.length; blockIndex += 1) {
      const block = asRecord(blocks[blockIndex]) || {};
      const blockKind = asString(block.kind).trim().toLowerCase();
      const blockContent = asString(block.content);
      const blockId = `s${stepIndex || 1}_b${blockIndex + 1}`;
      if (!blockContent.trim()) continue;
      if (blockKind === "math") {
        push(
          "BLOCK_SET_MATH",
          {
            step_index: stepIndex,
            block_id: blockId,
            latex: blockContent,
            display: block.display !== false,
          },
          120 + Math.floor(rand() * 80)
        );
        continue;
      }
      for (const chunk of chunkText(blockContent, 8, 16, rand)) {
        push(
          "BLOCK_APPEND_TEXT",
          {
            step_index: stepIndex,
            block_id: blockId,
            chunk,
          },
          16 + Math.floor(rand() * 18)
        );
      }
    }

    push("STEP_END", { step_index: stepIndex }, 90 + Math.floor(rand() * 50));
  }

  const finalAnswer = asRecord(item.final_answer) || null;
  if (finalAnswer) {
    const answerText = asString(finalAnswer.answer_text).trim();
    if (answerText) {
      for (const chunk of chunkText(answerText, 12, 20, rand)) {
        push("FINAL_APPEND_TEXT", { chunk }, 15 + Math.floor(rand() * 14));
      }
    }
    const answerLatex = asString(finalAnswer.answer_latex).trim();
    if (answerLatex) {
      push("FINAL_SET_MATH", { latex: answerLatex }, 130);
    }
    const valuesRaw = Array.isArray(finalAnswer.values) ? finalAnswer.values : [];
    if (valuesRaw.length > 0) {
      const values = valuesRaw
        .map((entry) => asRecord(entry))
        .filter((entry): entry is Record<string, unknown> => Boolean(entry))
        .map((entry) => ({
          key: asString(entry.key).trim(),
          text: isNonEmptyString(entry.text) ? entry.text : null,
          latex: isNonEmptyString(entry.latex) ? entry.latex : null,
          number: typeof entry.number === "number" ? entry.number : null,
          unit: isNonEmptyString(entry.unit) ? entry.unit : null,
        }))
        .filter((entry) => entry.key || entry.text || entry.latex || entry.number !== null);
      if (values.length > 0) {
        push("FINAL_VALUES_SET", { values }, 80);
      }
    }
  }

  const plot = asRecord(item.plot) || null;
  const shouldVisualize = Boolean(plot?.should_visualize);
  const recipe = asRecord(plot?.recipe);
  if (plot && shouldVisualize && recipe) {
    push("PLOT_SHOW", { plot }, 260 + Math.floor(rand() * 80));
  }

  const pythonCode = asString(plot?.python_code).trim();
  if (pythonCode) {
    push("PYTHON_CODE_SHOW", { code: pythonCode }, 120);
  }

  const results = asRecord(item.results) || null;
  const taskResults = Array.isArray(results?.task_results) ? results?.task_results : [];
  if (taskResults.length > 0) {
    push(
      "VERIFICATION_SET",
      { task_results: taskResults.filter((entry) => Boolean(asRecord(entry))) },
      70
    );
  }

  const quality = asRecord(item.quality) || null;
  if (quality) {
    const assumptions = Array.isArray(quality.assumptions) ? quality.assumptions : [];
    const warnings = Array.isArray(quality.warnings) ? quality.warnings : [];
    const confidence = typeof quality.confidence === "number" ? quality.confidence : null;
    if (assumptions.length > 0 || warnings.length > 0 || confidence !== null) {
      push("QUALITY_SET", { quality: { assumptions, warnings, confidence } }, 60);
    }
  }

  const context = asRecord(root.context) || null;
  if (context) {
    const filtered = Object.fromEntries(
      Object.entries(context).filter(([, value]) => {
        if (value === null || value === undefined) return false;
        if (typeof value === "string" && value.trim().length === 0) return false;
        return true;
      })
    );
    if (Object.keys(filtered).length > 0) {
      push("CONTEXT_SET", { context: filtered }, 60);
    }
  }

  push("MESSAGE_END", {}, 120);
  return events;
}

