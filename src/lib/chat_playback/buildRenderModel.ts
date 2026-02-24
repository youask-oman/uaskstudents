export interface RenderModelHeader {
  attempt_id: string | null;
  tier: string | null;
  schema_name: string | null;
  schema_version: string | null;
  response_language: string | null;
  mode: string | null;
  request_id: string | null;
}

export interface RenderModelItem {
  question: {
    summary: string | null;
    text: string;
    tasks: Array<{ task_index: number; task_label: string }>;
  };
  steps: Array<Record<string, unknown>>;
  final_answer: Record<string, unknown> | null;
  plot: Record<string, unknown> | null;
  verification: { task_results: Array<Record<string, unknown>> };
  quality: Record<string, unknown> | null;
  classification: {
    domain: string | null;
    detected_tasks: string[];
  };
  refusal: {
    is_refusal: boolean;
    refusal_code: string | null;
    refusal_message: string | null;
  } | null;
  raw_non_null: Record<string, unknown>;
}

export interface RenderModel {
  header: RenderModelHeader;
  context: Record<string, unknown>;
  items: RenderModelItem[];
  raw_non_null: Record<string, unknown>;
}

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;

const asString = (value: unknown): string | null => {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  }
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return null;
};

const asTasks = (value: unknown): Array<{ task_index: number; task_label: string }> => {
  const rows = Array.isArray(value) ? value : [];
  return rows
    .map((row, idx) => {
      const rec = asRecord(row);
      if (!rec) return null;
      const task_index = Number(rec.task_index ?? idx + 1);
      const task_label = asString(rec.task_label) || `Task ${idx + 1}`;
      return { task_index: Number.isFinite(task_index) ? task_index : idx + 1, task_label };
    })
    .filter((row): row is { task_index: number; task_label: string } => Boolean(row));
};

const asRecordArray = (value: unknown): Array<Record<string, unknown>> => {
  const rows = Array.isArray(value) ? value : [];
  return rows.map((row) => asRecord(row)).filter((row): row is Record<string, unknown> => Boolean(row));
};

const pruneNonNull = (value: unknown): unknown => {
  if (value === null || value === undefined) return undefined;
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : undefined;
  }
  if (Array.isArray(value)) {
    const next = value.map((row) => pruneNonNull(row)).filter((row) => row !== undefined);
    return next.length > 0 ? next : undefined;
  }
  if (typeof value === "object") {
    const rec = value as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const [key, row] of Object.entries(rec)) {
      const normalized = pruneNonNull(row);
      if (normalized !== undefined) out[key] = normalized;
    }
    return Object.keys(out).length > 0 ? out : undefined;
  }
  return value;
};

const asPrunedRecord = (value: unknown): Record<string, unknown> => {
  const pruned = pruneNonNull(value);
  return asRecord(pruned) || {};
};

export function buildRenderModel(structuredData: Record<string, unknown> | null | undefined): RenderModel {
  const root = asRecord(structuredData) || {};
  const items = Array.isArray(root.items) ? root.items : [];

  const header: RenderModelHeader = {
    attempt_id: asString(root.attempt_id),
    tier: asString(root.tier),
    schema_name: asString(root.schema_name),
    schema_version: asString(root.schema_version),
    response_language: asString(root.response_language),
    mode: asString(root.mode),
    request_id: asString(root.request_id),
  };

  const mappedItems: RenderModelItem[] = items
    .map((row) => asRecord(row))
    .filter((row): row is Record<string, unknown> => Boolean(row))
    .map((item) => {
      const classification = asRecord(item.classification) || {};
      const refusal = asRecord(item.refusal);
      const refusalModel = refusal
        ? {
            is_refusal: Boolean(refusal.is_refusal),
            refusal_code: asString(refusal.refusal_code),
            refusal_message: asString(refusal.refusal_message),
          }
        : null;
      return {
        question: {
          summary: asString(item.question_summary),
          text: asString(item.question_text) || "",
          tasks: asTasks(item.tasks),
        },
        steps: asRecordArray(item.steps),
        final_answer: asRecord(item.final_answer),
        plot: asRecord(item.plot),
        verification: {
          task_results: asRecordArray(asRecord(item.results)?.task_results),
        },
        quality: asRecord(item.quality),
        classification: {
          domain: asString(classification.domain),
          detected_tasks: (Array.isArray(classification.detected_tasks) ? classification.detected_tasks : [])
            .map((task) => asString(task))
            .filter((task): task is string => Boolean(task)),
        },
        refusal: refusalModel,
        raw_non_null: asPrunedRecord(item),
      };
    });

  return {
    header,
    context: asPrunedRecord(root.context),
    items: mappedItems,
    raw_non_null: asPrunedRecord(root),
  };
}

