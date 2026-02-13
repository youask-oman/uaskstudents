"use client";

import { use, useEffect, useMemo, useReducer, useState } from "react";
import { useSearchParams } from "next/navigation";
import DashboardNavBar from "@/components/DashboardNavBar";
import MathCanvasLayout from "@/components/math-canvas/MathCanvasLayout";
import LeftNotebookSidebar from "@/components/math-canvas/LeftNotebookSidebar";
import CanvasWorkspace from "@/components/math-canvas/CanvasWorkspace";
import RightTutorChat from "@/components/math-canvas/RightTutorChat";
import ShareSolutionModal from "@/components/share/ShareSolutionModal";
import {
  extractBatchSolutionsFromSessionMessages,
  extractPrimarySolution,
  flattenTextItems,
  normalizeSessionMessages,
  parseStepTitles,
} from "@/components/math-canvas/normalizer";
import { CanvasPageData, SavedPaperVersion, SessionMessage, StepRow } from "@/components/math-canvas/types";
import { buildInitialDocumentState, createPageId, documentReducer } from "@/components/math-canvas/documentModel";
import { DEMO_SOLUTION } from "@/lib/mock-response";
import { DEMO_BATCH_MESSAGES } from "@/lib/mock-batch-session";

interface ChatSessionPayload {
  id: number | string;
  attempt_id?: string | null;
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
  if (structured.mode === "batch_text_solve") return true;
  if (Array.isArray(structured.solutions) && structured.solutions.length > 0) return true;

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

const heuristicallyWrapMath = (text: string): string => {
  if (!text) return "";
  // If already has delimiters, leave it alone
  if (text.includes("\\(") || text.includes("\\[") || text.includes("$")) return text;

  // Pattern: "Solve for x, 2x + 7 = 19"
  const solveMatch = text.match(/^(Solve for\s+)([a-zA-Z])([,:]?\s*)(.+)$/i);
  if (solveMatch) {
    return `${solveMatch[1]}\\(${solveMatch[2]}\\)${solveMatch[3]}\\(${solveMatch[4].trim()}\\)`;
  }

  // Pattern: "Evaluate [math]"
  const evalMatch = text.match(/^(Evaluate|Simplify|Factor|Expand|Solve)([:\s]+)(.+)$/i);
  if (evalMatch) {
    return `${evalMatch[1]}${evalMatch[2]}\\(${evalMatch[3].trim()}\\)`;
  }

  // If it's just an equation like "y = mx + b" with no words
  if (/^[0-9a-zA-Z\s+\-*/^=().,]+$/.test(text) && /[=<>]=?/.test(text)) {
    // Check if it has too many words
    const words = text.split(/\s+/).filter(w => /[a-zA-Z]{2,}/.test(w));
    if (words.length <= 1) {
      return `\\(${text}\\)`;
    }
  }

  return text;
};

const buildInitialPages = (
  messages: ReturnType<typeof normalizeSessionMessages>,
  sessionTitle?: string
): CanvasPageData[] => {
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

  /* Extract first user message text to use as a fallback problem statement */
  const userMessage = messages.find((m) => m.role === "user");
  const userText = userMessage ? flattenTextItems(userMessage) : "";

  // Prioritize sessionTitle if valid, then layoutTitle, then recognizedLatex, then userText
  // Avoid using sessionTitle if it's generic like "Untitled Session"
  const validSessionTitle = sessionTitle && sessionTitle !== "Untitled Session" ? sessionTitle : undefined;
  const rawProblemStatement = validSessionTitle || layoutTitle || solution?.recognizedLatex || userText || "";
  const problemStatement = heuristicallyWrapMath(rawProblemStatement);

  if (solution && problemStatement) {
    blocks.push({
      id: "recognized-block",
      type: "recognition",
      latex: problemStatement,
      badge: "AI recognized",
    });
  }

  if (solution && (solution.steps.length > 0 || solution.result)) {
    blocks.push({
      id: "steps-block",
      type: "steps",
      steps: solution.steps,
      result: solution.result,
      finalAnswer: solution.finalAnswer,
      verificationChecks: solution.verificationChecks,
      domainConstraints: solution.domainConstraints,
      assumptions: solution.assumptions,
      originalProblem: solution.originalProblem,
      normalizedProblem: solution.normalizedProblem,
      commonMistakes: solution.commonMistakes,
      autocorrectApplied: solution.autocorrectApplied,
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

const buildBatchInitialPages = (
  batchSolutions: ReturnType<typeof extractBatchSolutionsFromSessionMessages>,
): CanvasPageData[] => {
  const page = createPage();
  page.title = batchSolutions.length > 0 ? `Batch Solve (${batchSolutions.length})` : "Batch Solve";
  const blocks = page.blocks || [];

  batchSolutions.forEach((entry, index) => {
    const questionLabel = `Question ${entry.questionId}`;
    const recognized = entry.questionText || entry.solution.recognizedLatex || questionLabel;

    blocks.push({
      id: `batch-recognition-${entry.questionId}-${index + 1}`,
      type: "recognition",
      latex: recognized,
      badge: questionLabel,
    });

    blocks.push({
      id: `batch-steps-${entry.questionId}-${index + 1}`,
      type: "steps",
      steps: Array.isArray(entry.solution.steps) ? entry.solution.steps : ([] as StepRow[]),
      result: entry.solution.result,
      finalAnswer: entry.solution.finalAnswer,
      verificationChecks: entry.solution.verificationChecks,
      domainConstraints: entry.solution.domainConstraints,
      assumptions: entry.solution.assumptions,
      originalProblem: entry.solution.originalProblem,
      normalizedProblem: entry.solution.normalizedProblem,
      commonMistakes: entry.solution.commonMistakes,
      autocorrectApplied: entry.solution.autocorrectApplied,
      plots: entry.solution.plots,
      confidence: entry.solution.confidence,
    });

    if (index < batchSolutions.length - 1) {
      blocks.push({
        id: `batch-separator-${entry.questionId}-${index + 1}`,
        type: "text",
        text: "__BATCH_SEPARATOR__",
      });
    }
  });

  if (blocks.length === 0) {
    blocks.push({
      id: "batch-empty-block",
      type: "text",
      text: "No parsed batch solutions found.",
    });
  }

  page.blocks = blocks;
  return [page];
};

export default function ChatPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const searchParams = useSearchParams();
  const [session, setSession] = useState<ChatSessionPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [documentState, dispatch] = useReducer(
    documentReducer,
    buildInitialDocumentState([createPage()], "none")
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
              model_used: "gpt-5-mini",
            },
          ],
        });
        setLoading(false);
        return;
      }
      if (id === "demo-batch") {
        setSession({
          id: "demo-batch",
          title: "Batch Solve Demo",
          subject: "Math",
          created_at: new Date().toISOString(),
          messages: DEMO_BATCH_MESSAGES,
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
  const batchSolutions = useMemo(
    () => extractBatchSolutionsFromSessionMessages(session?.messages || []),
    [session?.messages]
  );

  const tutorMessages = useMemo(() => {
    const all = session?.messages || [];
    const filtered = all.filter((message) => !isSolvePrimaryAssistantMessage(message));
    // Remove the very first message if it is a user prompt (redundant with canvas)
    if (filtered.length > 0 && filtered[0].role === "user") {
      return filtered.slice(1);
    }
    return filtered;
  }, [session?.messages]);

  const tutorNormalizedMessages = useMemo(
    () => normalizeSessionMessages(tutorMessages),
    [tutorMessages]
  );

  const primarySolution = useMemo(() => {
    if (batchSolutions.length > 0) return batchSolutions[0].solution;
    return extractPrimarySolution(normalizedMessages);
  }, [batchSolutions, normalizedMessages]);

  /* Compute best-attempt original problem statement */
  const originalProblemStatement = useMemo(() => {
    let text = "";
    if (session?.title && session.title !== "Untitled Session") text = session.title;
    else if (primarySolution?.layoutTitle) text = primarySolution.layoutTitle;
    else if (primarySolution?.recognizedLatex) text = primarySolution.recognizedLatex;
    else {
      const firstUserMsg = normalizedMessages.find(m => m.role === "user");
      text = firstUserMsg ? flattenTextItems(firstUserMsg) : "";
    }
    return heuristicallyWrapMath(text);
  }, [session?.title, primarySolution, normalizedMessages]);

  const outlineItems = useMemo<OutlineItem[]>(() => {
    const items: OutlineItem[] = [];
    const firstPage = documentState.pages[0];
    const blocks = firstPage?.blocks || [];
    const plots = (firstPage?.elements || []).filter((element) => element.type === "plot");

    blocks.forEach((block) => {
      if (block.type === "recognition") {
        const qMatch = block.id.match(/batch-recognition-([^-]+)-\d+$/);
        const qLabel = qMatch?.[1] ? `Question ${qMatch[1]}` : "Recognized Problem";
        items.push({ id: block.id, label: qLabel, tag: "RECOGNITION" });
      }
      if (block.type === "steps") {
        const qMatch = block.id.match(/batch-steps-([^-]+)-\d+$/);
        const qPrefix = qMatch?.[1] ? `${qMatch[1]} - ` : "";
        block.steps.forEach((step, index) => {
          const title = (step.title || "").trim();
          const generic = /^step\s+\d+$/i.test(title);
          items.push({
            id: `${block.id}-step-${index + 1}`,
            label: generic || !title ? `${qPrefix}Step ${index + 1}` : `${qPrefix}${title}`,
            tag: "STEP",
          });
        });
        items.push({ id: `${block.id}-final-answer`, label: `${qPrefix}Final Answer`, tag: "FINAL" });
        if (Array.isArray(block.verificationChecks) && block.verificationChecks.length > 0) {
          items.push({ id: `${block.id}-verification`, label: `${qPrefix}Verification`, tag: "VERIFY" });
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

  const stepTitles = useMemo(() => {
    if (batchSolutions.length > 0) {
      const all = batchSolutions.flatMap((entry) => parseStepTitles(entry.solution.steps || []));
      return Array.from(new Set(all)).slice(0, 12);
    }
    return parseStepTitles(primarySolution?.steps || []);
  }, [batchSolutions, primarySolution?.steps]);

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
      const grade_band = typeof entry.grade_band === "string" ? entry.grade_band : undefined;
      const difficulty = typeof entry.difficulty === "string" ? entry.difficulty : undefined;

      if (domain || topic || grade_band || difficulty) {
        return { domain, topic, grade_band, difficulty };
      }
    }
    return undefined;
  }, [session?.messages]);

  const savedPaperVersions = useMemo(
    () => getSavedPaperVersions(session?.messages || []),
    [session?.messages]
  );

  const shareAttemptId = useMemo(() => {
    if (session?.attempt_id && typeof session.attempt_id === "string") return session.attempt_id;
    const sourceMessages = session?.messages || [];
    for (let i = sourceMessages.length - 1; i >= 0; i -= 1) {
      const payload = sourceMessages[i].structured_data;
      if (!payload || typeof payload !== "object") continue;
      const raw = payload as Record<string, unknown>;
      const direct = raw.attempt_id;
      if (typeof direct === "string" && direct.trim()) return direct.trim();
      const solveMeta = raw.solve_meta;
      if (solveMeta && typeof solveMeta === "object") {
        const nestedAttempt = (solveMeta as Record<string, unknown>).attempt_id;
        if (typeof nestedAttempt === "string" && nestedAttempt.trim()) return nestedAttempt.trim();
      }
    }
    return null;
  }, [session?.attempt_id, session?.messages]);

  useEffect(() => {
    if (!session) return;
    const latestSavedPages = savedPaperVersions[0]?.pages;
    const initialPages = latestSavedPages && latestSavedPages.length > 0
      ? latestSavedPages
      : batchSolutions.length > 0
        ? buildBatchInitialPages(batchSolutions)
        : buildInitialPages(normalizedMessages, session.title || "");
    dispatch({
      type: "RESET",
      state: buildInitialDocumentState(initialPages, "none"),
    });
  }, [batchSolutions, normalizedMessages, savedPaperVersions, session]);

  const tokenUsage = useMemo(() => {
    let input = 0;
    let output = 0;
    let total = 0;
    (session?.messages || []).forEach((msg: SessionMessage) => {
      if (msg.role === "assistant") {
        const record = msg as unknown as Record<string, unknown>;
        const inT = Number(record.input_tokens || 0);
        const outT = Number(record.output_tokens || 0);
        const usedT = Number(record.tokens_used || 0);
        input += inT;
        output += outT;
        total += usedT || (inT + outT);
      }
    });
    return { input_tokens: input, output_tokens: output, total_tokens: total };
  }, [session?.messages]);

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

  const viewMode: "edit" | "student_report" =
    (searchParams.get("view") || "").toLowerCase() === "student_report" ? "student_report" : "edit";

  return (
    <>
      <MathCanvasLayout
        header={<DashboardNavBar />}
        leftSidebar={
          <LeftNotebookSidebar
            notebookTitle={notebookTitle}
            notebookSubtitle={notebookSubtitle}
            sessionId={String(session.id)}
            tokenUsage={tokenUsage}
            outlineItems={outlineItems}
            classification={classification}
            confidence={primarySolution?.confidence}
            onOutlineSelect={(targetId) => {
              const target = document.getElementById(targetId);
              if (!target) return;
              target.scrollIntoView({ behavior: "smooth", block: "start" });
            }}
          />
        }
        workspace={
          <CanvasWorkspace
            sessionId={String(session.id)}
            onOpenShare={() => setShareModalOpen(true)}
            savedVersions={savedPaperVersions}
            state={documentState}
            dispatch={dispatch}
            viewMode={viewMode}
          />
        }
        rightSidebar={
          <RightTutorChat
            sessionId={String(session.id)}
            initialMessages={tutorNormalizedMessages}
            originalProblem={originalProblemStatement}
            stepTitles={stepTitles}
            classification={classification}
          />
        }
      />
      <ShareSolutionModal
        open={shareModalOpen}
        attemptId={shareAttemptId}
        sessionId={String(session.id)}
        onClose={() => setShareModalOpen(false)}
      />
    </>
  );
}
