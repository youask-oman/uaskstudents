import type { StandardRenderEvent } from "@/lib/chat_playback/types";

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" ? (value as Record<string, unknown>) : null;

const asString = (value: unknown): string =>
  typeof value === "string" ? value : value === null || value === undefined ? "" : String(value);

const asNumber = (value: unknown): number => {
  const num = Number(value);
  return Number.isFinite(num) ? num : 0;
};

const toValues = (raw: unknown): Array<{
  key: string;
  text: string | null;
  latex: string | null;
  number: number | null;
  unit: string | null;
}> => {
  const values = Array.isArray(raw) ? raw : [];
  return values
    .map((entry) => asRecord(entry))
    .filter((entry): entry is Record<string, unknown> => Boolean(entry))
    .map((entry) => ({
      key: asString(entry.key).trim(),
      text: typeof entry.text === "string" && entry.text.trim() ? entry.text : null,
      latex: typeof entry.latex === "string" && entry.latex.trim() ? entry.latex : null,
      number: typeof entry.number === "number" ? entry.number : null,
      unit: typeof entry.unit === "string" && entry.unit.trim() ? entry.unit : null,
    }));
};

export function convertBackendRenderEventsToStandard(
  renderEvents: unknown[]
): StandardRenderEvent[] {
  const source = Array.isArray(renderEvents) ? renderEvents : [];
  const converted: StandardRenderEvent[] = [];

  const push = (
    id: string,
    at_ms: number,
    type: StandardRenderEvent["type"],
    payload: Record<string, unknown>
  ) => {
    converted.push({ id, at_ms, type, payload });
  };

  source.forEach((rawEvent, index) => {
    const event = asRecord(rawEvent) || {};
    const payload = asRecord(event.payload) || {};
    const id = asString(event.id).trim() || `std_remote_evt_${String(index + 1).padStart(5, "0")}`;
    const at_ms = asNumber(event.at_ms);
    const type = asString(event.type).trim().toUpperCase();

    switch (type) {
      case "MESSAGE_START":
        push(id, at_ms, "MESSAGE_START", {});
        break;
      case "QUESTION_SET":
        push(id, at_ms, "QUESTION_START", {});
        if (asString(payload.text).trim()) {
          push(`${id}_text`, at_ms + 1, "QUESTION_APPEND_TEXT", { chunk: asString(payload.text) });
        }
        break;
      case "STEP_START":
        push(id, at_ms, "STEP_START", {
          step_index: asNumber(payload.step_index),
          title: asString(payload.title),
        });
        break;
      case "BLOCK_APPEND_TEXT":
        push(id, at_ms, "BLOCK_APPEND_TEXT", {
          step_index: asNumber(payload.step_index),
          block_id: asString(payload.block_id),
          chunk: asString(payload.chunk),
        });
        break;
      case "BLOCK_SET_MATH":
        push(id, at_ms, "BLOCK_SET_MATH", {
          step_index: asNumber(payload.step_index),
          block_id: asString(payload.block_id),
          latex: asString(payload.latex),
          display: Boolean(payload.display),
        });
        break;
      case "STEP_END":
        push(id, at_ms, "STEP_END", {
          step_index: asNumber(payload.step_index),
        });
        break;
      case "FINAL_ANSWER_SET":
        if (asString(payload.answer_text).trim()) {
          push(id, at_ms, "FINAL_APPEND_TEXT", { chunk: asString(payload.answer_text) });
        }
        if (asString(payload.answer_latex).trim()) {
          push(`${id}_latex`, at_ms + 1, "FINAL_SET_MATH", { latex: asString(payload.answer_latex) });
        }
        if (Array.isArray(payload.values) && payload.values.length > 0) {
          push(`${id}_values`, at_ms + 2, "FINAL_VALUES_SET", { values: toValues(payload.values) });
        }
        break;
      case "PLOT_SET":
        push(id, at_ms, "PLOT_SHOW", {
          plot: {
            should_visualize: true,
            recipe: asRecord(payload.recipe),
            notes: asString(payload.notes) || null,
            attempt_id: asString(payload.attempt_id) || null,
          },
        });
        break;
      case "PYTHON_CODE_SET":
        if (asString(payload.code).trim()) {
          push(id, at_ms, "PYTHON_CODE_SHOW", { code: asString(payload.code) });
        }
        break;
      case "MESSAGE_END":
        push(id, at_ms, "MESSAGE_END", {});
        break;
      default:
        break;
    }
  });

  return converted.sort((a, b) => a.at_ms - b.at_ms);
}
