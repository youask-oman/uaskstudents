"use client";

import { useMemo, useReducer } from "react";
import CanvasWorkspace from "@/components/math-canvas/CanvasWorkspace";
import {
  extractPrimarySolution,
  flattenTextItems,
  normalizeSessionMessages,
} from "@/components/math-canvas/normalizer";
import {
  buildInitialDocumentState,
  createPageId,
  documentReducer,
} from "@/components/math-canvas/documentModel";
import { CanvasPageData, SessionMessage, StepRow } from "@/components/math-canvas/types";

interface PublicSharePayload {
  attempt_id: string;
  paper: Record<string, unknown>;
  problem: Record<string, unknown>;
  created_at?: string | null;
  visibility: "PUBLIC";
}

const createPage = (): CanvasPageData => ({
  id: createPageId(),
  blocks: [],
  elements: [],
});

const heuristicallyWrapMath = (text: string): string => {
  if (!text) return "";
  if (text.includes("\\(") || text.includes("\\[") || text.includes("$")) return text;
  const solveMatch = text.match(/^(Solve for\s+)([a-zA-Z])([,:]?\s*)(.+)$/i);
  if (solveMatch) {
    return `${solveMatch[1]}\\(${solveMatch[2]}\\)${solveMatch[3]}\\(${solveMatch[4].trim()}\\)`;
  }
  return text;
};

const buildPages = (messages: ReturnType<typeof normalizeSessionMessages>, fallbackProblem: string): CanvasPageData[] => {
  const solution = extractPrimarySolution(messages);
  const page = createPage();
  page.title = solution?.layoutTitle || "Shared Solution";
  const blocks = page.blocks || [];

  const userMessage = messages.find((msg) => msg.role === "user");
  const userText = userMessage ? flattenTextItems(userMessage) : "";
  const recognized = heuristicallyWrapMath(solution?.recognizedLatex || fallbackProblem || userText || "");

  if (recognized) {
    blocks.push({
      id: "recognized-block",
      type: "recognition",
      latex: recognized,
      badge: "AI recognized",
    });
  }

  if (solution && (solution.steps.length > 0 || solution.result)) {
    blocks.push({
      id: "steps-block",
      type: "steps",
      steps: solution.steps as StepRow[],
      result: solution.result,
      finalAnswer: solution.finalAnswer,
      verificationChecks: solution.verificationChecks,
      domainConstraints: solution.domainConstraints,
      assumptions: solution.assumptions,
      originalProblem: solution.originalProblem,
      normalizedProblem: solution.normalizedProblem,
      commonMistakes: solution.commonMistakes,
      autocorrectApplied: solution.autocorrectApplied,
      plots: solution.plots,
      confidence: solution.confidence,
    });
  }

  if (blocks.length === 0) {
    blocks.push({
      id: "fallback-block",
      type: "text",
      text: "This shared solution has no renderable content.",
    });
  }

  page.blocks = blocks;
  return [page];
};

export default function ShareReadonlyClient({ payload }: { payload: PublicSharePayload }) {
  const syntheticMessages = useMemo<SessionMessage[]>(
    () => [
      {
        id: "shared-assistant",
        role: "assistant",
        content: "Shared solution",
        structured_data: payload.paper,
        created_at: payload.created_at || undefined,
      },
    ],
    [payload.created_at, payload.paper]
  );
  const normalized = useMemo(() => normalizeSessionMessages(syntheticMessages), [syntheticMessages]);
  const original = useMemo(() => {
    const raw = (payload.problem?.normalized || payload.problem?.original || "") as string;
    return heuristicallyWrapMath(raw || "");
  }, [payload.problem]);
  const pages = useMemo(() => buildPages(normalized, original), [normalized, original]);
  const [state, dispatch] = useReducer(
    documentReducer,
    buildInitialDocumentState(pages, "none")
  );

  return (
    <div className="min-h-screen bg-slate-100">
      <div className="px-6 py-4 border-b border-slate-200 bg-white flex items-center justify-between">
        <div>
          <div className="text-sm font-bold text-slate-700">Shared Solution</div>
          <div className="text-xs text-slate-500">Read-only view</div>
        </div>
        <a
          href="/solve"
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-bold bg-primary text-white"
        >
          Open in App
        </a>
      </div>
      <CanvasWorkspace
        sessionId={`share-${payload.attempt_id}`}
        savedVersions={[]}
        state={state}
        dispatch={dispatch}
        viewMode="student_report"
      />
    </div>
  );
}

