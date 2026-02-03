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

export type ToolType =
  | "text"
  | "math"
  | "shape"
  | "compass"
  | "ruler"
  | "graph"
  | "eraser"
  | "palette";

export interface ElementStyle {
  color: string;
  strokeColor: string;
  strokeWidth: number;
  fillColor: string;
  fontSize: number;
}

export interface ElementBase {
  id: string;
  type: "text" | "math" | "shape" | "line" | "circle" | "plot";
  pageId: string;
  x: number;
  y: number;
  width: number;
  height: number;
  zIndex: number;
  style: ElementStyle;
  createdAt: number;
  updatedAt: number;
}

export interface TextElement extends ElementBase {
  type: "text";
  text: string;
}

export interface MathElement extends ElementBase {
  type: "math";
  latexRaw: string;
  renderMode: "inline" | "block";
  badge?: string;
}

export interface ShapeElement extends ElementBase {
  type: "shape";
  shapeKind: "rect";
}

export interface LineElement extends ElementBase {
  type: "line";
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  length: number;
}

export interface CircleElement extends ElementBase {
  type: "circle";
  radius: number;
  centerX: number;
  centerY: number;
}

export interface PlotDataPoint {
  x: number;
  y: number;
}

export interface PlotElement extends ElementBase {
  type: "plot";
  title: string;
  xLabel: string;
  yLabel: string;
  points: PlotDataPoint[];
}

export type CanvasElement = TextElement | MathElement | ShapeElement | LineElement | CircleElement | PlotElement;

export interface StepRow {
  title: string;
  explanation?: string;
  mathLatex?: string;
}

export interface VerificationCheck {
  checkId: string;
  verdict: "pass" | "warn" | "fail" | "unknown";
  message: string;
  relatedStepId?: number | null;
  evidenceMath?: string;
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
  verificationChecks?: VerificationCheck[];
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
  | { id: string; type: "steps"; steps: StepRow[]; result?: string; verificationChecks?: VerificationCheck[] }
  | { id: string; type: "text"; text: string };

export interface SelectionState {
  elementIds: string[];
}

export interface ClipboardPayload {
  elements: CanvasElement[];
  sourcePageId: string;
}

export interface DocumentSnapshot {
  pages: CanvasPageData[];
  activePageId: string;
  selection: SelectionState;
}

export interface CanvasDocumentState extends DocumentSnapshot {
  activeTool: ToolType;
  clipboard: ClipboardPayload | null;
  past: DocumentSnapshot[];
  future: DocumentSnapshot[];
}

export interface CanvasPageData {
  id: string;
  title?: string;
  blocks?: CanvasBlock[];
  elements: CanvasElement[];
}
