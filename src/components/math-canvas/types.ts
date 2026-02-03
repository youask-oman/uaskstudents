export interface SessionMessage {
  id?: string | number;
  role: "user" | "assistant" | string;
  content: unknown;
  media_url?: string | null;
  structured_data?: Record<string, unknown> | null;
  created_at?: string;
  model_used?: string;
  tokens_used?: number;
  telemetry?: Record<string, unknown> | null;
  chart?: Record<string, unknown> | null;
  plot?: Record<string, unknown> | null;
}

export interface StepRow {
  title: string;
  explanation?: string;
  mathLatex?: string;
}

export interface PlotPoint {
  x: number;
  y: number;
  label?: string;
}

export interface ChartPayload {
  title?: string;
  xLabel?: string;
  yLabel?: string;
  points: PlotPoint[];
}

export interface MathSolutionPayload {
  recognizedLatex?: string;
  steps: StepRow[];
  result?: string;
  plots?: ChartPayload[];
}

export type NormalizedContentItem =
  | { type: "text"; text: string }
  | { type: "math_solution"; payload: MathSolutionPayload }
  | { type: "chart"; payload: ChartPayload }
  | { type: "error"; message: string };

export interface NormalizedChatMessage {
  id: string;
  role: "user" | "assistant";
  createdAt?: string;
  modelUsed?: string;
  items: NormalizedContentItem[];
}

export type CanvasBlock =
  | { id: string; type: "recognition"; latex: string; badge?: string }
  | { id: string; type: "steps"; steps: StepRow[]; result?: string }
  | { id: string; type: "text"; text: string };

export interface CanvasPageData {
  id: string;
  blocks: CanvasBlock[];
}
