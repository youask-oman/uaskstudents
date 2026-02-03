"use client";

import { use, useEffect, useMemo, useReducer, useState } from "react";
import DashboardNavBar from "@/components/DashboardNavBar";
import MathCanvasLayout from "@/components/math-canvas/MathCanvasLayout";
import LeftNotebookSidebar from "@/components/math-canvas/LeftNotebookSidebar";
import CanvasWorkspace from "@/components/math-canvas/CanvasWorkspace";
import RightTutorChat from "@/components/math-canvas/RightTutorChat";
import {
  extractPrimarySolution,
  flattenTextItems,
  normalizeSessionMessages,
  parseStepTitles,
} from "@/components/math-canvas/normalizer";
import { CanvasPageData, SessionMessage } from "@/components/math-canvas/types";
import { buildInitialDocumentState, createPageId, documentReducer } from "@/components/math-canvas/documentModel";
import { DEMO_SOLUTION } from "@/lib/mock-response";

interface ChatSessionPayload {
  id: number | string;
  title: string;
  subject?: string;
  created_at: string;
  is_saved?: boolean;
  messages: SessionMessage[];
}

interface OutlineItem {
  id: string;
  label: string;
  tag: string;
}

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" ? (value as Record<string, unknown>) : null;

const isSolvePrimaryAssistantMessage = (message: SessionMessage): boolean => {
  if (message.role !== "assistant") return false;

  const telemetry = asRecord(message.telemetry);
  if (telemetry?.hide_from_tutor === true) return true;
  if (telemetry?.channel === "canvas_primary") return true;

  const structured = asRecord(message.structured_data);
  if (!structured) return false;
  if (structured.hide_from_tutor === true) return true;
  if (structured.solve_meta) return true;

  const outputFormat = typeof structured.output_format === "string" ? structured.output_format.toLowerCase() : "";
  if (outputFormat === "freeform" || outputFormat === "json_schema") return true;

  if (structured.schema_version && asRecord(structured.question) && asRecord(structured.solution)) return true;
  return false;
};

const createPage = (): CanvasPageData => ({
  id: createPageId(),
  blocks: [],
  elements: [],
});

const buildInitialPages = (messages: ReturnType<typeof normalizeSessionMessages>): CanvasPageData[] => {
  const solution = extractPrimarySolution(messages);
  const firstPage = createPage();
  const now = Date.now();
  const firstStepTitle = solution?.steps?.[0]?.title?.trim();
  if (firstStepTitle) {
    firstPage.title = firstStepTitle;
  }
  const blocks = firstPage.blocks || [];

  if (solution?.recognizedLatex) {
    blocks.push({
      id: "recognized-block",
      type: "recognition",
      latex: solution.recognizedLatex,
      badge: "AI recognized",
    });
  }

  if (solution && (solution.steps.length > 0 || solution.result)) {
    blocks.push({
      id: "steps-block",
      type: "steps",
      steps: solution.steps,
      result: solution.result,
      verificationChecks: solution.verificationChecks,
    });
  }

  const latestAssistantText = [...messages]
    .reverse()
    .find((message) => message.role === "assistant");
  const latestText = latestAssistantText ? flattenTextItems(latestAssistantText) : "";

  if (latestText && (blocks.length === 0 || (solution?.steps.length ?? 0) <= 1)) {
    blocks.push({
      id: "text-block",
      type: "text",
      text: latestText,
    });
  }

  if (blocks.length === 0) {
    blocks.push({
      id: "empty-block",
      type: "text",
      text: "No parsed solution yet. Try solving again.",
    });
  }

  if (solution?.plots?.length) {
    firstPage.elements = solution.plots
      .filter((plot) => Array.isArray(plot.points) && plot.points.length >= 2)
      .map((plot, index) => ({
        id: `plot-element-${index + 1}`,
        type: "plot" as const,
        pageId: firstPage.id,
        x: 24,
        y: 24 + index * 290,
        width: 720,
        height: 270,
        zIndex: 100 + index,
        style: {
          color: "#1e293b",
          strokeColor: "#1e293b",
          strokeWidth: 2,
          fillColor: "#ffffff",
          fontSize: 14,
        },
        createdAt: now + index,
        updatedAt: now + index,
        title: plot.title || `Plot ${index + 1}`,
        xLabel: plot.xLabel || "x",
        yLabel: plot.yLabel || "y",
        points: plot.points.map((point) => ({ x: Number(point.x), y: Number(point.y) })),
      }));
  }

  firstPage.blocks = blocks;

  return [firstPage];
};

export default function ChatPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [session, setSession] = useState<ChatSessionPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [documentState, dispatch] = useReducer(
    documentReducer,
    buildInitialDocumentState([createPage()], "text")
  );

  useEffect(() => {
    const fetchSession = async () => {
      if (id === "demo-1") {
        setSession({
          id: "demo-1",
          title: "Math Canvas Demo",
          subject: "Calculus",
          created_at: new Date().toISOString(),
          messages: [
            {
              id: "demo-user",
              role: "user",
              content: "Evaluate: \\int_0^5 (3x^2 + 2x)\\,dx",
              created_at: new Date().toISOString(),
            },
            {
              id: "demo-assistant",
              role: "assistant",
              content: "Structured solution",
              structured_data:
                typeof DEMO_SOLUTION === "object" && DEMO_SOLUTION !== null
                  ? (DEMO_SOLUTION as Record<string, unknown>)
                  : null,
              created_at: new Date().toISOString(),
              model_used: "mightykatun/qwen2.5-math:7b",
            },
          ],
        });
        setLoading(false);
        return;
      }

      try {
        const response = await fetch(`/api/v1/sessions/${id}`);
        if (!response.ok) throw new Error("Failed to load session");
        const payload = (await response.json()) as ChatSessionPayload;
        setSession(payload);
      } catch (error) {
        console.error("Failed to load session", error);
        setSession(null);
      } finally {
        setLoading(false);
      }
    };

    if (id) void fetchSession();
  }, [id]);

  const normalizedMessages = useMemo(
    () => normalizeSessionMessages(session?.messages || []),
    [session?.messages]
  );

  const tutorMessages = useMemo(
    () => (session?.messages || []).filter((message) => !isSolvePrimaryAssistantMessage(message)),
    [session?.messages]
  );

  const tutorNormalizedMessages = useMemo(
    () => normalizeSessionMessages(tutorMessages),
    [tutorMessages]
  );

  const primarySolution = useMemo(
    () => extractPrimarySolution(normalizedMessages),
    [normalizedMessages]
  );

  const outlineItems = useMemo<OutlineItem[]>(() => {
    const items: OutlineItem[] = [];
    if (primarySolution?.recognizedLatex) {
      items.push({ id: "recognized-block", label: "Recognized Problem", tag: "RECOGNITION" });
    }
    if (primarySolution?.steps?.length) {
      primarySolution.steps.forEach((step, index) => {
        const title = (step.title || "").trim();
        const generic = /^step\s+\d+$/i.test(title);
        items.push({
          id: `steps-block-step-${index + 1}`,
          label: generic || !title ? `Step ${index + 1}` : title,
          tag: "STEP",
        });
      });
      items.push({ id: "steps-block-final-answer", label: "Final Answer", tag: "FINAL" });
    }
    if (primarySolution?.verificationChecks?.length) {
      items.push({ id: "steps-block-verification", label: "Verification", tag: "VERIFY" });
    }
    if (primarySolution?.plots?.length) {
      primarySolution.plots.forEach((plot, index) => {
        items.push({
          id: `plot-element-${index + 1}`,
          label: plot.title || `Plot ${index + 1}`,
          tag: "PLOT",
        });
      });
    }
    return items;
  }, [primarySolution]);

  const stepTitles = useMemo(
    () => parseStepTitles(primarySolution?.steps || []),
    [primarySolution?.steps]
  );

  const classification = useMemo(() => {
    const sourceMessages = session?.messages || [];
    for (let i = sourceMessages.length - 1; i >= 0; i -= 1) {
      const payload = sourceMessages[i].structured_data;
      if (!payload || typeof payload !== "object") continue;
      const rawClassification = (payload as Record<string, unknown>).classification;
      if (!rawClassification || typeof rawClassification !== "object") continue;
      const entry = rawClassification as Record<string, unknown>;
      const domain = typeof entry.domain === "string" ? entry.domain : undefined;
      const topic = typeof entry.topic === "string" ? entry.topic : undefined;
      if (domain || topic) {
        return { domain, topic };
      }
    }
    return undefined;
  }, [session?.messages]);

  useEffect(() => {
    if (!session) return;
    const initialPages = buildInitialPages(normalizedMessages);
    dispatch({
      type: "RESET",
      state: buildInitialDocumentState(initialPages, "text"),
    });
  }, [normalizedMessages, session]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--app-bg)]">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-[var(--primary-color)]" />
      </div>
    );
  }

  if (!session) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--app-bg)] text-slate-500">
        Session not found.
      </div>
    );
  }

  const notebookTitle = session.subject || "Math Notebook";
  const notebookSubtitle = session.title || "Untitled Session";
  const usagePercent = Math.max(15, Math.min(90, Math.round((normalizedMessages.length / 20) * 100)));

  return (
    <>
      <MathCanvasLayout
        header={<DashboardNavBar />}
        leftSidebar={
          <LeftNotebookSidebar
            notebookTitle={notebookTitle}
            notebookSubtitle={notebookSubtitle}
            usagePercent={usagePercent}
            outlineItems={outlineItems}
          />
        }
        workspace={
          <CanvasWorkspace
            state={documentState}
            dispatch={dispatch}
          />
        }
        rightSidebar={
          <RightTutorChat
            sessionId={String(session.id)}
            initialMessages={tutorNormalizedMessages}
            originalProblem={primarySolution?.recognizedLatex || ""}
            stepTitles={stepTitles}
            classification={classification}
          />
        }
      />
    </>
  );
}
