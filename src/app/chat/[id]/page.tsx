"use client";

import { use, useEffect, useMemo, useState } from "react";
import MathCanvasLayout from "@/components/math-canvas/MathCanvasLayout";
import LeftNotebookSidebar from "@/components/math-canvas/LeftNotebookSidebar";
import TopHeader from "@/components/math-canvas/TopHeader";
import CanvasWorkspace from "@/components/math-canvas/CanvasWorkspace";
import RightTutorChat from "@/components/math-canvas/RightTutorChat";
import LatexEditor from "@/components/math-canvas/LatexEditor";
import {
  extractPrimarySolution,
  flattenTextItems,
  normalizeSessionMessages,
  parseStepTitles,
} from "@/components/math-canvas/normalizer";
import { CanvasPageData, SessionMessage } from "@/components/math-canvas/types";
import { DEMO_SOLUTION } from "@/lib/mock-response";

interface ChatSessionPayload {
  id: number | string;
  title: string;
  subject?: string;
  created_at: string;
  is_saved?: boolean;
  messages: SessionMessage[];
}

const createPage = (): CanvasPageData => ({
  id: `page-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
  blocks: [],
});

const buildInitialPages = (messages: ReturnType<typeof normalizeSessionMessages>): CanvasPageData[] => {
  const solution = extractPrimarySolution(messages);
  const firstPage = createPage();

  if (solution?.recognizedLatex) {
    firstPage.blocks.push({
      id: `block-${Date.now()}-recognized`,
      type: "recognition",
      latex: solution.recognizedLatex,
      badge: "AI recognized",
    });
  }

  if (solution && (solution.steps.length > 0 || solution.result)) {
    firstPage.blocks.push({
      id: `block-${Date.now()}-steps`,
      type: "steps",
      steps: solution.steps,
      result: solution.result,
    });
  }

  if (firstPage.blocks.length === 0) {
    const latestAssistantText = [...messages]
      .reverse()
      .find((message) => message.role === "assistant");
    if (latestAssistantText) {
      const text = flattenTextItems(latestAssistantText);
      if (text) {
        firstPage.blocks.push({
          id: `block-${Date.now()}-text`,
          type: "text",
          text,
        });
      }
    }
  }

  return [firstPage];
};

export default function ChatPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [session, setSession] = useState<ChatSessionPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [pages, setPages] = useState<CanvasPageData[]>([]);
  const [activePageId, setActivePageId] = useState("");
  const [latexEditorOpen, setLatexEditorOpen] = useState(false);

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

  const primarySolution = useMemo(
    () => extractPrimarySolution(normalizedMessages),
    [normalizedMessages]
  );

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
    setPages(initialPages);
    setActivePageId(initialPages[0]?.id || "");
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
        header={<TopHeader notebookTitle={notebookTitle} />}
        leftSidebar={
          <LeftNotebookSidebar
            notebookTitle={notebookTitle}
            notebookSubtitle={notebookSubtitle}
            usagePercent={usagePercent}
          />
        }
        workspace={
          <CanvasWorkspace
            pages={pages}
            activePageId={activePageId}
            onSelectPage={setActivePageId}
            onAddPage={() => {
              const page = createPage();
              setPages((prev) => [...prev, page]);
              setActivePageId(page.id);
            }}
            onOpenLatexEditor={() => setLatexEditorOpen(true)}
          />
        }
        rightSidebar={
          <RightTutorChat
            sessionId={String(session.id)}
            initialMessages={normalizedMessages}
            originalProblem={primarySolution?.recognizedLatex || ""}
            stepTitles={stepTitles}
            classification={classification}
          />
        }
      />

      {latexEditorOpen ? (
        <LatexEditor
          key={`${activePageId}-${latexEditorOpen ? "open" : "closed"}`}
          onClose={() => setLatexEditorOpen(false)}
          onInsert={(latex) => {
            if (!activePageId) return;
            setPages((prev) =>
              prev.map((page) =>
                page.id === activePageId
                  ? {
                      ...page,
                      blocks: [
                        ...page.blocks,
                        {
                          id: `block-${Date.now()}-latex`,
                          type: "recognition",
                          latex,
                          badge: "AI recognized",
                        },
                      ],
                    }
                  : page
              )
            );
          }}
        />
      ) : null}
    </>
  );
}
