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
import { CanvasPageData, SavedPaperVersion, SessionMessage, ShortSourcePayload, StepRow } from "@/components/math-canvas/types";
import { buildInitialDocumentState, createPageId, documentReducer } from "@/components/math-canvas/documentModel";
import { DEMO_SOLUTION } from "@/lib/mock-response";
import { DEMO_BATCH_MESSAGES } from "@/lib/mock-batch-session";
import { resolvePlaybackFromMessage, type PlaybackSegment } from "@/lib/chat_final_playback";

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

type SolveTier = "SHORT_STEPS" | "STANDARD" | "RESEARCH" | "FINAL";

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" ? (value as Record<string, unknown>) : null;
const asString = (value: unknown): string | null =>
  typeof value === "string" ? value : (typeof value === "number" || typeof value === "boolean" ? String(value) : null);

const extractSessionMessageText = (message: SessionMessage): string => {
  const direct = asString(message.content);
  if (direct && direct.trim()) return direct;
  if (Array.isArray(message.content)) {
    const chunks = message.content
      .map((item) => {
        const obj = asRecord(item);
        if (!obj) return "";
        const text = asString(obj.text);
        if (text) return text;
        const nested = asRecord(obj.content);
        return asString(nested?.text) || "";
      })
      .filter((part) => part.trim().length > 0);
    if (chunks.length > 0) return chunks.join("\n");
  }
  return "";
};

const normalizeSolveTier = (value: unknown): SolveTier | null => {
  if (typeof value !== "string") return null;
  const normalized = value.trim().toUpperCase();
  if (!normalized) return null;
  if (normalized === "SHORT" || normalized === "SHORT_STEPS") return "SHORT_STEPS";
  if (normalized === "STANDARD") return "STANDARD";
  if (normalized === "RESEARCH") return "RESEARCH";
  if (normalized === "FINAL") return "FINAL";
  return null;
};

const inferSessionSolveTier = (session: ChatSessionPayload | null): SolveTier => {
  if (!session) return "FINAL";
  const messages = Array.isArray(session.messages) ? session.messages : [];
  const candidates: unknown[] = [];

  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    const structured = asRecord(message.structured_data);
    const telemetry = asRecord(message.telemetry);
    const solveMeta = asRecord(structured?.solve_meta);

    candidates.push(
      structured?.tier,
      structured?.tier_effective,
      structured?.tier_requested,
      structured?.effective_tier,
      solveMeta?.tier,
      solveMeta?.tier_effective,
      solveMeta?.tier_requested,
      solveMeta?.effective_tier,
      telemetry?.tier,
      telemetry?.tier_effective,
      telemetry?.tier_requested,
      telemetry?.effective_tier
    );
  }

  for (const candidate of candidates) {
    const tier = normalizeSolveTier(candidate);
    if (tier) return tier;
  }
  return "FINAL";
};

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
  let normalized = text
    .replace(/\\\\\(/g, "\\(")
    .replace(/\\\\\)/g, "\\)")
    .replace(/\\\\\[/g, "\\[")
    .replace(/\\\\\]/g, "\\]");
  normalized = normalized.replace(/\\text\{([^}]*)\}/g, "$1");
  // If already has delimiters, leave it alone
  if (normalized.includes("\\(") || normalized.includes("\\[") || normalized.includes("$")) return normalized;
  if (/\\[a-zA-Z]+/.test(normalized)) return normalized;

  // Pattern: "Solve for x, 2x + 7 = 19"
  const solveMatch = normalized.match(/^(Solve for\s+)([a-zA-Z])([,:]?\s*)(.+)$/i);
  if (solveMatch) {
    return `${solveMatch[1]}\\(${solveMatch[2]}\\)${solveMatch[3]}\\(${solveMatch[4].trim()}\\)`;
  }

  // Pattern: "Evaluate [math]"
  const evalMatch = normalized.match(/^(Evaluate|Simplify|Factor|Expand|Solve)([:\s]+)(.+)$/i);
  if (evalMatch) {
    return `${evalMatch[1]}${evalMatch[2]}\\(${evalMatch[3].trim()}\\)`;
  }

  // Pattern: "Find the inverse of f(x) = (x-1)/(x+2)"
  const inverseMatch = normalized.match(/^(Find\s+the\s+inverse\s+of\s+)(.+)$/i);
  if (inverseMatch) {
    return `${inverseMatch[1]}\\(${inverseMatch[2].trim()}\\)`;
  }

  // Generic inline equation inside prose.
  const inlineEquation = /([A-Za-z][A-Za-z0-9_]*\([^)]*\)\s*=\s*[^,.;\n]+|[A-Za-z][A-Za-z0-9_]*\s*=\s*[^,.;\n]+)/;
  if (inlineEquation.test(normalized)) {
    return normalized.replace(inlineEquation, (expr) => `\\(${expr.trim()}\\)`);
  }

  // If it's just an equation like "y = mx + b" with no words
  if (/^[0-9a-zA-Z\s+\-*/^=().,]+$/.test(normalized) && /[=<>]=?/.test(normalized)) {
    // Check if it has too many words
    const words = normalized.split(/\s+/).filter(w => /[a-zA-Z]{2,}/.test(w));
    if (words.length <= 1) {
      return `\\(${normalized}\\)`;
    }
  }

  return normalized;
};

const extractRecognitionLatex = (text: string): string => {
  const normalized = (text || "")
    .trim()
    .replace(/\\\\\(/g, "\\(")
    .replace(/\\\\\)/g, "\\)")
    .replace(/\\\\\[/g, "\\[")
    .replace(/\\\\\]/g, "\\]");
  if (!normalized) return "";

  const inlineDelimited = normalized.match(/\\\((.+?)\\\)/);
  if (inlineDelimited?.[1]) return inlineDelimited[1].trim();
  const blockDelimited = normalized.match(/\\\[(.+?)\\\]/);
  if (blockDelimited?.[1]) return blockDelimited[1].trim();
  const dollarDelimited = normalized.match(/\$(.+?)\$/);
  if (dollarDelimited?.[1]) return dollarDelimited[1].trim();

  const inverseMatch = normalized.match(/^(?:Find\s+the\s+inverse\s+of\s+|inverse\s+)(.+)$/i);
  if (inverseMatch?.[1]) return inverseMatch[1].trim();

  const solveMatch = normalized.match(/^(?:Solve\s+for\s+[a-zA-Z]\s*[,:]?\s*)(.+)$/i);
  if (solveMatch?.[1]) return solveMatch[1].trim();

  const eqMatch = normalized.match(/([A-Za-z][A-Za-z0-9_]*\([^)]*\)\s*=\s*[^,.;\n]+|[A-Za-z][A-Za-z0-9_]*\s*=\s*[^,.;\n]+)/);
  if (eqMatch?.[1]) return eqMatch[1].trim();

  return normalized;
};

const isLocalSympySolution = (solution: {
  steps?: StepRow[];
  finalAnswer?: { answer_text?: string | null };
} | null | undefined): boolean => {
  if (!solution) return false;
  const steps = Array.isArray(solution.steps) ? solution.steps : [];
  const markerInSteps = steps.some((step) => {
    const title = String(step?.title || "").toLowerCase();
    const explanation = String(step?.explanation || "").toLowerCase();
    return (
      title.includes("local result") ||
      explanation.includes("sympy") ||
      explanation.includes("numpy")
    );
  });
  if (markerInSteps) return true;
  const answerText = String(solution.finalAnswer?.answer_text || "").toLowerCase();
  return answerText.includes("sympy") || answerText.includes("numpy");
};

const extractShortSourcePayload = (messages: SessionMessage[]): ShortSourcePayload | null => {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message.role !== "assistant") continue;
    const structured = asRecord(message.structured_data);
    if (!structured) continue;

    const rawCandidate = asRecord(structured.raw_user_extraction) || structured;
    const sections = Array.isArray(rawCandidate.sections)
      ? (rawCandidate.sections as ShortSourcePayload["sections"])
      : [];
    if (sections.length === 0) continue;

    const questionText =
      asString(asRecord(structured.problem)?.original_text) ||
      asString(asRecord(structured.question)?.text) ||
      undefined;

    return {
      sections,
      global_final_answer: asString(rawCandidate.global_final_answer) || undefined,
      warnings: Array.isArray(rawCandidate.warnings) ? rawCandidate.warnings : undefined,
      meta: asRecord(rawCandidate.meta) || undefined,
      question: questionText,
      model: message.model_used || undefined,
    };
  }
  return null;
};

const extractAssistantPlaybackSource = (
  messages: SessionMessage[]
): {
  messageId: string;
  assistantContent: string;
  segments: PlaybackSegment[];
  source: string;
  structuredData?: Record<string, unknown> | null;
} | null => {
  const assistantMessages = [...messages]
    .reverse()
    .filter((message) => String(message?.role || "").toLowerCase() === "assistant");
  const prioritized = [
    ...assistantMessages.filter((message) => isSolvePrimaryAssistantMessage(message)),
    ...assistantMessages.filter((message) => !isSolvePrimaryAssistantMessage(message)),
  ];

  for (const message of prioritized) {
    const messageIdRaw = message?.id;
    const messageId = messageIdRaw === undefined || messageIdRaw === null ? "" : String(messageIdRaw).trim();
    if (!messageId) continue;

    const resolved = resolvePlaybackFromMessage(message);
    const assistantContent = (resolved.content || extractSessionMessageText(message) || "").trim();
    return {
      messageId,
      assistantContent,
      segments: Array.isArray(resolved.segments) ? resolved.segments : [],
      source: resolved.source,
      structuredData: asRecord(message.structured_data),
    };
  }
  return null;
};

const buildInitialPages = (
  messages: ReturnType<typeof normalizeSessionMessages>,
  sessionTitle?: string,
  options?: {
    shortTier?: boolean;
    shortSource?: ShortSourcePayload | null;
    shortPlayback?: {
      messageId: string;
      assistantContent: string;
      segments: PlaybackSegment[];
      source: string;
      structuredData?: Record<string, unknown> | null;
    } | null;
  }
): CanvasPageData[] => {
  const isShortTier = Boolean(options?.shortTier);
  const shortSource = options?.shortSource || null;
  const shortPlayback = options?.shortPlayback || null;
  const solution = extractPrimarySolution(messages);
  const localSympy = isLocalSympySolution(solution);
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

  // Prefer full problem text from structured payload first; session title can be truncated.
  // Avoid using sessionTitle if it's generic like "Untitled Session"
  const validSessionTitle = sessionTitle && sessionTitle !== "Untitled Session" ? sessionTitle : undefined;
  const rawProblemStatement =
    solution?.originalProblem ||
    (isShortTier ? shortSource?.question : undefined) ||
    userText ||
    validSessionTitle ||
    layoutTitle ||
    solution?.recognizedLatex ||
    "";
  const problemStatement = rawProblemStatement;
  const recognitionLatex = heuristicallyWrapMath((problemStatement || "").trim());

  if (!isShortTier && solution && recognitionLatex) {
    blocks.push({
      id: "recognized-block",
      type: "recognition",
      latex: recognitionLatex,
      badge: "AI recognized",
    });
  }

  if (
    (solution && (solution.steps.length > 0 || solution.result || solution.plotPayload || solution.pythonCode)) ||
    (isShortTier && shortSource?.sections?.length)
  ) {
    const shortResult = shortSource?.global_final_answer || solution?.result;
    blocks.push({
      id: "steps-block",
      type: "steps",
      steps: localSympy ? [] : (solution?.steps || []),
      shortSections: localSympy ? undefined : solution?.shortSections,
      shortSource: isShortTier ? shortSource || undefined : undefined,
      result: isShortTier ? shortResult : solution?.result,
      finalAnswer: localSympy && solution?.finalAnswer
        ? { ...solution.finalAnswer, values: [] }
        : (isShortTier ? undefined : solution?.finalAnswer),
      verificationChecks: isShortTier ? undefined : solution?.verificationChecks,
      domainConstraints: isShortTier ? undefined : solution?.domainConstraints,
      assumptions: isShortTier ? undefined : solution?.assumptions,
      originalProblem: localSympy ? undefined : solution?.originalProblem,
      normalizedProblem: localSympy ? undefined : solution?.normalizedProblem,
      commonMistakes: isShortTier ? undefined : solution?.commonMistakes,
      autocorrectApplied: isShortTier ? undefined : solution?.autocorrectApplied,
      plotPayload: isShortTier ? undefined : solution?.plotPayload,
      pythonCode: isShortTier ? undefined : solution?.pythonCode,
      playbackMessageId: shortPlayback?.messageId,
      playbackFallbackContent: shortPlayback?.assistantContent,
      playbackSegments: shortPlayback?.segments,
      playbackSource: shortPlayback?.source,
      playbackStructuredData: shortPlayback?.structuredData,
    });
  }

  const latestAssistantText = [...messages]
    .reverse()
    .find((message) => message.role === "assistant");
  const latestText = latestAssistantText ? flattenTextItems(latestAssistantText) : "";

  if (latestText && blocks.length === 0) {
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
        y: 24 + index * 440,
        width: 760,
        height: 420,
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
    const localSympy = isLocalSympySolution(entry.solution);
    const recognizedRaw =
      entry.solution.originalProblem ||
      entry.questionText ||
      entry.solution.recognizedLatex ||
      questionLabel;
    const recognized = heuristicallyWrapMath((recognizedRaw || "").trim());

    blocks.push({
      id: `batch-recognition-${entry.questionId}-${index + 1}`,
      type: "recognition",
      latex: recognized,
      badge: questionLabel,
    });

    blocks.push({
      id: `batch-steps-${entry.questionId}-${index + 1}`,
      type: "steps",
      steps: localSympy
        ? []
        : (Array.isArray(entry.solution.steps) ? entry.solution.steps : ([] as StepRow[])),
      shortSections: localSympy ? undefined : entry.solution.shortSections,
      result: entry.solution.result,
      finalAnswer: localSympy && entry.solution.finalAnswer
        ? { ...entry.solution.finalAnswer, values: [] }
        : entry.solution.finalAnswer,
      verificationChecks: entry.solution.verificationChecks,
      domainConstraints: entry.solution.domainConstraints,
      assumptions: entry.solution.assumptions,
      originalProblem: localSympy ? undefined : entry.solution.originalProblem,
      normalizedProblem: localSympy ? undefined : entry.solution.normalizedProblem,
      commonMistakes: entry.solution.commonMistakes,
      autocorrectApplied: entry.solution.autocorrectApplied,
      plots: entry.solution.plots,
      plotPayload: entry.solution.plotPayload,
      pythonCode: entry.solution.pythonCode,
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

export default function ChatFinalPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const searchParams = useSearchParams();
  const [session, setSession] = useState<ChatSessionPayload | null>(null);
  const [layoutDirection, setLayoutDirection] = useState<"ltr" | "rtl">("ltr");
  const [resolvedAttemptId, setResolvedAttemptId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [documentState, dispatch] = useReducer(
    documentReducer,
    buildInitialDocumentState([createPage()], "none")
  );

  useEffect(() => {
        const normalizeLanguageCode = (value: string): string => {
      const raw = (value || "").trim().toLowerCase();
      const map: Record<string, string> = {
        en: "en",
        english: "en",
        "english (us)": "en",
        ar: "ar",
        arabic: "ar",
        "\u0627\u0644\u0639\u0631\u0628\u064a\u0629": "ar",
        fr: "fr",
        french: "fr",
        francais: "fr",
        "fran\u00e7ais": "fr",
        es: "es",
        spanish: "es",
        espanol: "es",
        "espa\u00f1ol": "es",
        pt: "pt",
        portuguese: "pt",
        portugues: "pt",
        "portugu\u00eas": "pt",
        ru: "ru",
        russian: "ru",
        "\u0440\u0443\u0441\u0441\u043a\u0438\u0439": "ru",
        it: "it",
        italian: "it",
        italiano: "it",
      };
      return map[raw] || raw.slice(0, 2);
    };

    const fetchLanguagePreference = async () => {
      if (typeof window === "undefined") return;
      const rawUserId = localStorage.getItem("user_id");
      if (!rawUserId) return;
      const userId = Number(rawUserId);
      if (!Number.isFinite(userId) || userId <= 0) return;
      try {
        const res = await fetch(`/api/v1/user/profile?user_id=${userId}`);
        if (!res.ok) return;
        const payload = (await res.json()) as { preferred_language?: string | null };
        const lang = normalizeLanguageCode(payload.preferred_language || "");
        setLayoutDirection(lang === "ar" ? "rtl" : "ltr");
      } catch {
        setLayoutDirection("ltr");
      }
    };

    void fetchLanguagePreference();
  }, []);

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
        if (!response.ok) {
          let detail = "";
          try {
            const body = await response.json();
            detail =
              (typeof body?.detail === "string" && body.detail) ||
              (typeof body?.error?.message === "string" && body.error.message) ||
              "";
          } catch {
            detail = "";
          }
          const suffix = detail ? `: ${detail}` : "";
          throw new Error(`Failed to load session${suffix}`);
        }
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
  const solveTier = useMemo(() => inferSessionSolveTier(session), [session]);
  const shortSourcePayload = useMemo(
    () => (solveTier === "SHORT_STEPS" ? extractShortSourcePayload(session?.messages || []) : null),
    [session?.messages, solveTier]
  );
  const shortPlaybackSource = useMemo(
    () => extractAssistantPlaybackSource(session?.messages || []),
    [session?.messages]
  );
  useEffect(() => {
    if (!shortPlaybackSource) return;
    console.log("[chat_final] playback_source", {
      messageId: shortPlaybackSource.messageId,
      source: shortPlaybackSource.source,
      contentLen: shortPlaybackSource.assistantContent.length,
      segments: shortPlaybackSource.segments.length,
    });
  }, [shortPlaybackSource]);
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
        const hasShortSections = Array.isArray(block.shortSections) && block.shortSections.length > 0;
        const hasShortSourceSections = Array.isArray(block.shortSource?.sections) && block.shortSource.sections.length > 0;
        const hasPlayback =
          typeof block.playbackMessageId === "string" &&
          block.playbackMessageId.trim().length > 0 &&
          typeof block.playbackFallbackContent === "string" &&
          block.playbackFallbackContent.trim().length > 0;
        const isShortOutline = hasShortSections || hasShortSourceSections || hasPlayback;

        if (isShortOutline) {
          const questionSuffix = (qMatch?.[1] || "Q1").toUpperCase();
          const questionTag = `QUESTION ${questionSuffix}`;
          const solutionAnchorId = hasShortSections
              ? `${block.id}-section-0`
              : hasShortSourceSections
                ? `${block.id}-source-section-0`
                : `${block.id}-playback-solution`;
          items.push({ id: `${block.id}-problem`, label: `Question ${questionSuffix}`, tag: questionTag });

          if (hasPlayback && Array.isArray(block.playbackSegments) && block.playbackSegments.length > 0) {
            const playbackStepTitles = block.playbackSegments
              .filter((segment) => segment.kind === "step_title")
              .map((segment) => String(segment.text || "").trim())
              .filter(Boolean);

            if (playbackStepTitles.length > 0) {
              playbackStepTitles.forEach((title, index) => {
                items.push({
                  id: `${block.id}-playback-step-${index + 1}`,
                  label: title,
                  tag: "STEP",
                });
              });
            } else {
              items.push({ id: solutionAnchorId, label: "Solution", tag: "SOLUTION" });
            }
          } else {
            items.push({ id: solutionAnchorId, label: "Solution", tag: "SOLUTION" });
          }

          items.push({ id: `${block.id}-final-answer`, label: "Final Answer", tag: "FINAL" });
          return;
        }

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
      const root = payload as Record<string, unknown>;
      const candidates: Record<string, unknown>[] = [];
      const rootClassification = root.classification;
      if (rootClassification && typeof rootClassification === "object") {
        candidates.push(rootClassification as Record<string, unknown>);
      }
      const items = Array.isArray(root.items) ? root.items : [];
      for (const item of items) {
        if (!item || typeof item !== "object") continue;
        const itemClassification = (item as Record<string, unknown>).classification;
        if (itemClassification && typeof itemClassification === "object") {
          candidates.push(itemClassification as Record<string, unknown>);
        }
      }

      for (const entry of candidates) {
        const domain = typeof entry.domain === "string" ? entry.domain : undefined;
        const topic = typeof entry.topic === "string" ? entry.topic : undefined;
        const grade_band = typeof entry.grade_band === "string" ? entry.grade_band : undefined;
        const difficulty = typeof entry.difficulty === "string" ? entry.difficulty : undefined;
        if (domain || topic || grade_band || difficulty) {
          return { domain, topic, grade_band, difficulty };
        }
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
    if (!session?.id) return;
    if (shareAttemptId) {
      setResolvedAttemptId(shareAttemptId);
      return;
    }
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) return;

    const run = async () => {
      try {
        const resp = await fetch(`/api/v1/shares/session/${encodeURIComponent(String(session.id))}/attempt`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!resp.ok) return;
        const payload = (await resp.json()) as { attempt_id?: string | null };
        if (payload.attempt_id && payload.attempt_id.trim()) {
          setResolvedAttemptId(payload.attempt_id.trim());
        }
      } catch {
        // keep null; paper will show unavailable state
      }
    };
    void run();
  }, [session?.id, shareAttemptId]);

  const effectiveAttemptId = shareAttemptId || resolvedAttemptId || null;

  useEffect(() => {
    if (!session) return;
    const latestSavedPages = savedPaperVersions[0]?.pages;
    const isShortTierSession = solveTier === "SHORT_STEPS";
    const initialPages = latestSavedPages && latestSavedPages.length > 0
      ? latestSavedPages
      : (!isShortTierSession && batchSolutions.length > 0)
        ? buildBatchInitialPages(batchSolutions)
        : buildInitialPages(normalizedMessages, session.title || "", {
          shortTier: isShortTierSession,
          shortSource: shortSourcePayload,
          shortPlayback: shortPlaybackSource,
        });
    dispatch({
      type: "RESET",
      state: buildInitialDocumentState(initialPages, "none"),
    });
  }, [batchSolutions, normalizedMessages, savedPaperVersions, session, shortPlaybackSource, shortSourcePayload, solveTier]);

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

  const isFinalTier = solveTier === "FINAL";
  const tierLabel = solveTier === "SHORT_STEPS" ? "SHORT STEPS" : solveTier;

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--app-bg)]" dir={layoutDirection}>
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-[var(--primary-color)]" />
      </div>
    );
  }

  if (!session) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--app-bg)] text-slate-500" dir={layoutDirection}>
        Session not found.
      </div>
    );
  }

  const notebookTitle = session.subject ? `${tierLabel} - ${session.subject}` : `${tierLabel} Math Notebook`;
  const baseSubtitleRaw = session.title || "Untitled Session";
  const baseSubtitle =
    solveTier === "SHORT_STEPS" && baseSubtitleRaw.length > 30
      ? `${baseSubtitleRaw.slice(0, 30)}...`
      : baseSubtitleRaw;
  const notebookSubtitle = baseSubtitle.toUpperCase().startsWith(tierLabel)
    ? baseSubtitle
    : `${tierLabel} Paper - ${baseSubtitle}`;

  const viewMode: "edit" | "student_report" =
    (searchParams.get("view") || "").toLowerCase() === "student_report" ? "student_report" : "edit";

  return (
    <div dir={layoutDirection} className="bg-amber-50/30 dark:bg-amber-950/10">
      <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs font-medium text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300">
        {isFinalTier
          ? "FINAL Tier Workspace - Structured paper rendering for final-grade output"
          : `${tierLabel} Tier Workspace - Structured paper rendering for short-step output`}
      </div>
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
            attemptId={effectiveAttemptId}
            solveTier={solveTier}
            onOpenShare={() => setShareModalOpen(true)}
            savedVersions={savedPaperVersions}
            state={documentState}
            dispatch={dispatch}
            viewMode={viewMode}
            hideStepLabels={isFinalTier}
            paperVariant={isFinalTier ? "final_handwritten" : "short_paper"}
          />
        }
        rightSidebar={
          <RightTutorChat
            sessionId={String(session.id)}
            initialMessages={tutorNormalizedMessages}
            sourceMessages={session?.messages || []}
            originalProblem={originalProblemStatement}
            stepTitles={stepTitles}
            classification={classification}
            direction={layoutDirection}
          />
        }
      />
      <ShareSolutionModal
        open={shareModalOpen}
        attemptId={effectiveAttemptId}
        sessionId={String(session.id)}
        onClose={() => setShareModalOpen(false)}
      />
    </div>
  );
}

