export interface SessionMessage {
  id?: string | number;
  role: "user" | "assistant" | string;
  content: unknown;
  display_markdown?: string | null;
  rendered_content?: string | null;
  media_url?: string | null;
  structured_data?: Record<string, unknown> | null;
  created_at?: string;
  model_used?: string;
  tokens_used?: number;
  telemetry?: Record<string, unknown> | null;
  chart?: Record<string, unknown> | null;
  plot?: Record<string, unknown> | null;
}

export interface PlaybackSegment {
  kind: "step_title" | "markdown" | "math" | "final_answer";
  text: string;
}

export type ToolType =
  | "none"
  | "select"
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
  type: "text" | "math" | "shape" | "line" | "circle" | "plot" | "image";
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
  richTextHtml?: string;
  richTextJson?: Record<string, unknown>;
}

export type RichTextStyleOption =
  | "title"
  | "subtitle"
  | "heading"
  | "subheading"
  | "section"
  | "subsection"
  | "body";

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

export interface ImageElement extends ElementBase {
  type: "image";
  src: string;
  alt?: string;
  aspectRatio?: number;
}

export type CanvasElement = TextElement | MathElement | ShapeElement | LineElement | CircleElement | PlotElement | ImageElement;


export interface StepRow {
  k?: number;
  title: string;
  titleRichHtml?: string;
  titleRichJson?: Record<string, unknown>;
  bodyMarkdown?: string;
  explanation?: string;
  explanationRichHtml?: string;
  explanationRichJson?: Record<string, unknown>;
  mathLatex?: string;
  mathRichHtml?: string;
  mathRichJson?: Record<string, unknown>;
  rulesUsed?: string[];
  checks?: string[];
  notes?: string;
}

export interface ShortSectionBlock {
  kind: string;
  content: string;
}

export interface ShortSectionStep {
  index: number;
  kind: string;
  raw?: string;
  blocks: ShortSectionBlock[];
}

export interface ShortSection {
  label: string;
  heading: string;
  steps: ShortSectionStep[];
  finalAnswer?: string;
  incomplete?: boolean;
}

export interface ShortSourceStepBlock {
  kind?: string;
  content?: string;
}

export interface ShortSourceStep {
  index?: number;
  kind?: string;
  blocks?: ShortSourceStepBlock[];
  raw?: string;
}

export interface ShortSourceSection {
  label?: string;
  heading?: string;
  steps?: ShortSourceStep[];
  final_answer?: string;
  incomplete?: boolean;
  incomplete_diag?: Record<string, unknown> | null;
}

export interface ShortSourcePayload {
  sections: ShortSourceSection[];
  global_final_answer?: string;
  warnings?: unknown[];
  meta?: Record<string, unknown>;
  question?: string;
  model?: string;
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
  expressionLatex?: string;
  points: PlotPoint[];
}

export interface FinalAnswerValue {
  label: string;
  value: string | number | boolean | Record<string, unknown> | null;
  value_latex?: string;
  key?: string;
  unit?: string;
}

export interface FinalAnswer {
  answer_text: string;
  answer_latex: string;
  values: FinalAnswerValue[];
  units?: string;
}

export interface MathSolutionPayload {
  layoutTitle?: string;
  recognizedLatex?: string;
  assumptions?: string[];
  originalProblem?: string;
  normalizedProblem?: string;
  domainConstraints?: string[];
  steps: StepRow[];
  result?: string;
  finalAnswer?: FinalAnswer;
  plots?: ChartPayload[];
  plotPayload?: Record<string, unknown>;
  pythonCode?: string;
  verificationChecks?: VerificationCheck[];
  autocorrectApplied?: boolean;
  confidence?: number;
  commonMistakes?: string[];
  parseStatus?: "ok" | "partial" | "failed";
  shortSections?: ShortSection[];
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
  | {
    id: string;
    type: "steps";
    steps: StepRow[];
    result?: string;
    verificationChecks?: VerificationCheck[];
    domainConstraints?: string[];
    autocorrectApplied?: boolean;
    assumptions?: string[];
    originalProblem?: string;
    normalizedProblem?: string;
    finalAnswer?: FinalAnswer;
    plots?: ChartPayload[];
    plotPayload?: Record<string, unknown>;
    pythonCode?: string;
    confidence?: number;
    commonMistakes?: string[];
    shortSections?: ShortSection[];
    shortSource?: ShortSourcePayload;
    playbackMessageId?: string;
    playbackFallbackContent?: string;
    playbackSegments?: PlaybackSegment[];
    playbackSource?: string;
  }
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

export interface SavedPaperVersion {
  key: string;
  version: number;
  title: string;
  savedAt: string;
  pages: CanvasPageData[];
}
