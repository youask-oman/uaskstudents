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
import { CanvasPageData, SavedPaperVersion, SessionMessage } from "@/components/math-canvas/types";
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

const asSavedPage = (value: unknown): CanvasPageData | null => {
  const record = asRecord(value);
  if (!record) return null;
  const elements = Array.isArray(record.elements) ? record.elements : [];
  const blocks = Array.isArray(record.blocks) ? record.blocks : [];
  return {
    id: typeof record.id === "string" && record.id.trim() ? record.id : createPageId(),
    title: typeof record.title === "string" ? record.title : undefined,
    blocks: blocks as CanvasPageData["blocks"],
    elements: elements as CanvasPageData["elements"],
  };
};

const getSavedPaperVersions = (messages: SessionMessage[]): SavedPaperVersion[] => {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message.role !== "assistant") continue;
    const structured = asRecord(message.structured_data);
    if (!structured) continue;
    const versions = structured.paper_versions;
    if (!Array.isArray(versions) || versions.length === 0) continue;
    const parsed: SavedPaperVersion[] = versions
      .map((rawVersion, index) => {
        const versionObj = asRecord(rawVersion);
        if (!versionObj || !Array.isArray(versionObj.pages)) return null;
        const pages = versionObj.pages.map(asSavedPage).filter((page): page is CanvasPageData => Boolean(page));
        if (pages.length === 0) return null;
        const versionNumberRaw = Number(versionObj.version);
        const version = Number.isFinite(versionNumberRaw) && versionNumberRaw > 0 ? versionNumberRaw : index + 1;
        const savedAt = typeof versionObj.saved_at === "string" ? versionObj.saved_at : "";
        const title = typeof versionObj.title === "string" && versionObj.title.trim()
          ? versionObj.title.trim()
          : `Version ${version}`;
        return {
          key: `${version}-${savedAt || index}`,
          version,
          title,
          savedAt,
          pages,
        };
      })
      .filter((item): item is SavedPaperVersion => Boolean(item))
      .sort((left, right) => right.version - left.version);
    if (parsed.length > 0) return parsed;
  }
  return [];
};

const buildInitialPages = (messages: ReturnType<typeof normalizeSessionMessages>): CanvasPageData[] => {
  const solution = extractPrimarySolution(messages);
  const firstPage = createPage();
  const now = Date.now();
  const layoutTitle = solution?.layoutTitle?.trim();
  const firstStepTitle = solution?.steps?.[0]?.title?.trim();
  if (layoutTitle) {
    firstPage.title = layoutTitle;
  } else if (firstStepTitle) {
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
        title: layoutTitle || plot.title || `Plot ${index + 1}`,
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
    const firstPage = documentState.pages[0];
    const blocks = firstPage?.blocks || [];
    const plots = (firstPage?.elements || []).filter((element) => element.type === "plot");

    blocks.forEach((block) => {
      if (block.type === "recognition") {
        items.push({ id: block.id, label: "Recognized Problem", tag: "RECOGNITION" });
      }
      if (block.type === "steps") {
        block.steps.forEach((step, index) => {
          const title = (step.title || "").trim();
          const generic = /^step\s+\d+$/i.test(title);
          items.push({
            id: `${block.id}-step-${index + 1}`,
            label: generic || !title ? `Step ${index + 1}` : title,
            tag: "STEP",
          });
        });
        items.push({ id: `${block.id}-final-answer`, label: "Final Answer", tag: "FINAL" });
        if (Array.isArray(block.verificationChecks) && block.verificationChecks.length > 0) {
          items.push({ id: `${block.id}-verification`, label: "Verification", tag: "VERIFY" });
        }
      }
      if (block.type === "text") {
        items.push({ id: block.id, label: "Notes", tag: "NOTE" });
      }
    });

    if (plots.length > 0) {
      plots.forEach((plot, index) => {
        items.push({
          id: plot.id,
          label: plot.title || `Plot ${index + 1}`,
          tag: "PLOT",
        });
      });
    } else if (primarySolution?.plots?.length) {
      primarySolution.plots.forEach((plot, index) => {
        items.push({
          id: `plot-element-${index + 1}`,
          label: plot.title || `Plot ${index + 1}`,
          tag: "PLOT",
        });
      });
    }
    return items;
  }, [documentState.pages, primarySolution]);

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

  const savedPaperVersions = useMemo(
    () => getSavedPaperVersions(session?.messages || []),
    [session?.messages]
  );

  useEffect(() => {
    if (!session) return;
    const latestSavedPages = savedPaperVersions[0]?.pages;
    const initialPages = latestSavedPages && latestSavedPages.length > 0
      ? latestSavedPages
      : buildInitialPages(normalizedMessages);
    dispatch({
      type: "RESET",
      state: buildInitialDocumentState(initialPages, "text"),
    });
  }, [normalizedMessages, savedPaperVersions, session]);

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
            sessionId={String(session.id)}
            savedVersions={savedPaperVersions}
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
