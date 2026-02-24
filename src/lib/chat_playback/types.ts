export type StandardRenderEventType =
  | "MESSAGE_START"
  | "QUESTION_START"
  | "QUESTION_APPEND_SUMMARY"
  | "QUESTION_APPEND_TEXT"
  | "TASKS_SET"
  | "STEP_START"
  | "BLOCK_APPEND_TEXT"
  | "BLOCK_SET_MATH"
  | "STEP_END"
  | "FINAL_APPEND_TEXT"
  | "FINAL_SET_MATH"
  | "FINAL_VALUES_SET"
  | "PLOT_SHOW"
  | "PYTHON_CODE_SHOW"
  | "VERIFICATION_SET"
  | "QUALITY_SET"
  | "CONTEXT_SET"
  | "MESSAGE_END";

export interface StandardRenderEvent {
  id: string;
  at_ms: number;
  type: StandardRenderEventType;
  payload: Record<string, unknown>;
}

export interface StandardPlaybackBlock {
  id: string;
  kind: "text" | "math";
  text?: string;
  latex?: string;
  display?: boolean;
}

export interface StandardPlaybackStep {
  stepIndex: number;
  title: string;
  blocks: StandardPlaybackBlock[];
  done?: boolean;
}

export interface FinalAnswerValue {
  key: string;
  text: string | null;
  latex: string | null;
  number: number | null;
  unit: string | null;
}

export interface StandardPlaybackState {
  questionSummary: string;
  questionText: string;
  tasks: Array<{ task_index: number; task_label: string }>;
  steps: StandardPlaybackStep[];
  finalAnswerText: string;
  finalAnswerLatex: string;
  finalAnswerValues: FinalAnswerValue[];
  plot: Record<string, unknown> | null;
  pythonCode: string;
  verificationResults: Array<Record<string, unknown>>;
  quality: Record<string, unknown> | null;
  context: Record<string, unknown> | null;
  isTyping: boolean;
  isComplete: boolean;
  activeStepIndex: number | null;
}

