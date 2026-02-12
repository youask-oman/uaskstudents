"use client";

import "@mdxeditor/editor/style.css";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import DashboardNavBar from "@/components/DashboardNavBar";
import MathJaxRenderer from "@/components/math/MathJaxRenderer";
import { parseSolutionDocFromStructured } from "@/components/math-canvas/normalizer";
import type { CanvasBlock, CanvasPageData, FinalAnswer, MathSolutionPayload } from "@/components/math-canvas/types";
import {
    exportCanvasToDocx,
    exportCanvasToPdf,
    hasExportableSolution,
    SolutionExportPayload,
} from "@/components/math-canvas/export/exportDocument";
import { API_BASE_URL, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";
import {
    MDXEditor,
    toolbarPlugin,
    KitchenSinkToolbar,
    listsPlugin,
    linkPlugin,
    linkDialogPlugin,
    headingsPlugin,
    markdownShortcutPlugin,
    quotePlugin,
    codeBlockPlugin,
    codeMirrorPlugin,
    tablePlugin,
    thematicBreakPlugin,
    imagePlugin,
} from "@mdxeditor/editor";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";

const MAX_CONTENT_BYTES = 50_000;

// Help links (required by spec):
// MDXEditor Getting Started: https://mdxeditor.dev/editor/docs/getting-started
// MDXEditor GitHub: https://github.com/mdx-editor/editor
// MDX math guide: https://mdxjs.com/guides/math/
// Markdown syntax: https://www.markdownguide.org/basic-syntax/

const InsertInlineMath = ({ onInsert }: { onInsert: (snippet: string) => void }) => (
    <button
        type="button"
        className="rounded border border-slate-200 px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50"
        onClick={() => onInsert("$x^2 + 1$")}
        title="Insert inline math ($...$)"
    >
        Inline $...$
    </button>
);

const InsertBlockMath = ({ onInsert }: { onInsert: (snippet: string) => void }) => (
    <button
        type="button"
        className="rounded border border-slate-200 px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50"
        onClick={() => onInsert(`\n$$\n\\int_0^1 x^2 \\, dx = \\frac{1}{3}\n$$\n`)}
        title="Insert block math ($$ ... $$)"
    >
        Block $$...$$
    </button>
);

const NULL_SECTION_TITLES = new Set([
    "domain constraints",
    "verification",
    "assumptions",
    "common mistakes",
    "notes",
    "checks",
    "graphs",
]);

const isNullishLine = (line: string) => {
    const trimmed = line.trim();
    if (!trimmed) return true;
    if (/^(none|n\/a|null|n\\a)\s*$/i.test(trimmed)) return true;
    if (/^[-*+\\u2022]\s*(none|n\/a|null|n\\a)\s*$/i.test(trimmed)) return true;
    if (/^\*\*LaTeX:\*\*\s*(\$\$\s*)?(none|n\/a|null|n\\a)(\s*\$\$)?$/i.test(trimmed)) return true;
    if (/^(latex|laTeX)\s*:\s*(none|n\/a|null|n\\a)\s*$/i.test(trimmed)) return true;
    return false;
};

const cleanPreviewMarkdown = (markdown: string) => {
    const lines = markdown.split(/\r?\n/);
    const result: string[] = [];
    const isHeading = (line: string) => /^\s*#{1,6}\s+/.test(line);
    const headingLevel = (line: string) => {
        const match = line.match(/^\s*(#{1,6})\s+/);
        return match ? match[1].length : 0;
    };
    const isEmptyContent = (sectionLines: string[]) => {
        const trimmed = sectionLines.map((line) => line.trim()).filter((line) => line.length > 0);
        if (trimmed.length === 0) return true;
        return trimmed.every((line) => isNullishLine(line));
    };

    let i = 0;
    while (i < lines.length) {
        const line = lines[i];
        if (!isHeading(line)) {
            if (!isNullishLine(line)) {
                result.push(line);
            }
            i += 1;
            continue;
        }
        const level = headingLevel(line);
        const title = line.replace(/^#{1,6}\s+/, "").trim().toLowerCase();
        let j = i + 1;
        while (j < lines.length) {
            if (isHeading(lines[j]) && headingLevel(lines[j]) <= level) break;
            j += 1;
        }
        const sectionLines = lines.slice(i + 1, j);
        if (isEmptyContent(sectionLines)) {
            if (!NULL_SECTION_TITLES.has(title)) {
                result.push(line);
            }
            i = j;
            continue;
        }
        const cleaned = sectionLines.filter((sectionLine) => !isNullishLine(sectionLine));
        result.push(line, ...cleaned);
        i = j;
    }
    return result.join("\n");
};

const autoWrapBareLatexLine = (line: string) => {
    const trimmed = line.trim();
    if (!trimmed) return line;
    if (trimmed.includes("$") || trimmed.includes("\\(") || trimmed.includes("\\[")) return line;
    const hasLatexCommand = /\\(frac|sqrt|text|int|sum|theta|alpha|beta|gamma|pi|sin|cos|tan|log|ln|cdot|times|leq|geq|neq|pm|rightarrow|left|right|quad|qquad|infty)/.test(trimmed);
    if (!hasLatexCommand) return line;
    const startsWithTextCommand = /^\\text\{[\s\S]*\}/.test(trimmed);
    if (startsWithTextCommand) {
        return `$${trimmed}$`;
    }
    const nonLatexWords = trimmed.replace(/\\[a-zA-Z]+/g, "").match(/[a-zA-Z]{3,}/g);
    if (nonLatexWords && nonLatexWords.length > 0) return line;
    return `$${trimmed}$`;
};

const normalizeMarkdownForPreview = (
    markdown: string,
    options: { cleanPreview: boolean; autoWrapMath: boolean }
) => {
    if (!markdown) return "";
    let output = markdown;
    if (options.cleanPreview) {
        output = cleanPreviewMarkdown(output);
    }
    if (options.autoWrapMath) {
        const lines = output.split(/\r?\n/);
        let inFence = false;
        output = lines
            .map((raw) => {
                const line = raw;
                if (/^```/.test(line.trim())) {
                    inFence = !inFence;
                    return line;
                }
                if (inFence) return line;
                let normalizedLine = autoWrapBareLatexLine(line);
                // Normalize common Unicode math operators to LaTeX so prose math can typeset them.
                normalizedLine = normalizedLine
                    .replace(/≠/g, "\\neq ")
                    .replace(/≤/g, "\\leq ")
                    .replace(/≥/g, "\\geq ");
                // Final answer lines often come as plain text. Wrap RHS when it looks math-like.
                const finalTextMatch = normalizedLine.match(/^(\s*Text:\s*)(.+)$/i);
                if (finalTextMatch) {
                    const rhs = finalTextMatch[2].trim();
                    const hasMathish = /[\\^_=+\-*/()]/.test(rhs) || /\\(?:neq|leq|geq)\b/.test(rhs);
                    if (hasMathish && !rhs.includes("$") && !rhs.includes("\\(") && !rhs.includes("\\[")) {
                        normalizedLine = `${finalTextMatch[1]}$${rhs}$`;
                    }
                }
                return normalizedLine;
            })
            .join("\n");
    }
    output = output.replace(/\\\(([\s\S]*?)\\\)/g, (_match, inner) => `$${inner.trim()}$`);
    output = output.replace(/\\\[([\s\S]*?)\\\]/g, (_match, inner) => `$$\n${inner.trim()}\n$$`);
    return output;
};

const MarkdownPreview = ({
    content,
    cleanPreview,
    autoWrapMath,
}: {
    content: string;
    cleanPreview: boolean;
    autoWrapMath: boolean;
}) => {
    type MarkdownChildrenProps = { children?: ReactNode };
    const flattenText = (node: ReactNode): string => {
        if (node === null || node === undefined || typeof node === "boolean") return "";
        if (typeof node === "string" || typeof node === "number") return String(node);
        if (Array.isArray(node)) return node.map((child) => flattenText(child)).join("");
        if (typeof node === "object" && "props" in (node as { props?: unknown })) {
            const childProps = (node as { props?: { children?: ReactNode } }).props;
            return flattenText(childProps?.children);
        }
        return "";
    };

    const renderMathAwareText = (children?: ReactNode, className?: string, listItem = false) => {
        const text = flattenText(children).trim();
        if (!text) {
            return listItem ? <li className={className}>{children}</li> : <div className={className}>{children}</div>;
        }
        if (listItem) {
            return (
                <li className={className}>
                    <MathJaxRenderer content={text} mode="prose" />
                </li>
            );
        }
        return (
            <div className={className}>
                <MathJaxRenderer content={text} mode="prose" />
            </div>
        );
    };

    const markdownComponents: Record<string, React.ComponentType<MarkdownChildrenProps>> = {
        h1: ({ children }) => <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{children}</h1>,
        h2: ({ children }) => <h2 className="text-xl font-bold text-slate-900 dark:text-white">{children}</h2>,
        h3: ({ children }) => <h3 className="text-lg font-bold text-slate-900 dark:text-white">{children}</h3>,
        p: ({ children }) => renderMathAwareText(children, "text-slate-700 dark:text-slate-200", false),
        li: ({ children }) => renderMathAwareText(children, "text-slate-700 dark:text-slate-200", true),
        math: ({ children }) => (
            <div className="my-3">
                <MathJaxRenderer content={String(children ?? "")} mode="block" />
            </div>
        ),
        inlineMath: ({ children }) => (
            <MathJaxRenderer content={String(children ?? "")} mode="inline" />
        ),
    };
    const normalized = normalizeMarkdownForPreview(content || "", { cleanPreview, autoWrapMath });
    if (!normalized.trim()) {
        return <div className="text-sm text-slate-500">No content yet.</div>;
    }
    return (
        <div className="space-y-4">
            <ReactMarkdown
                remarkPlugins={[remarkMath]}
                components={markdownComponents}
            >
                {normalized}
            </ReactMarkdown>
        </div>
    );
};

const buildFinalAnswer = (doc: Record<string, unknown> | null): FinalAnswer | undefined => {
    if (!doc) return undefined;
    const finalAnswer = doc.final_answer as Record<string, unknown> | undefined;
    if (!finalAnswer) return undefined;
    const answer_text = typeof finalAnswer.text === "string" ? finalAnswer.text : "";
    const answer_latex = typeof finalAnswer.latex === "string" ? finalAnswer.latex : "";
    if (!answer_text && !answer_latex) return undefined;
    return {
        answer_text,
        answer_latex,
        values: [],
    };
};

const buildExportPages = (solutionDoc: Record<string, unknown> | null): CanvasPageData[] => {
    if (!solutionDoc) return [];
    const payload = parseSolutionDocFromStructured({ solution_doc: solutionDoc }) as MathSolutionPayload | null;
    if (!payload) return [];
    const blocks: CanvasBlock[] = [];
    if (payload.recognizedLatex) {
        blocks.push({
            id: "recognition-block",
            type: "recognition",
            latex: payload.recognizedLatex,
            badge: "AI recognized",
        });
    }
    blocks.push({
        id: "steps-block",
        type: "steps",
        steps: payload.steps || [],
        result: payload.result,
        verificationChecks: payload.verificationChecks,
        domainConstraints: payload.domainConstraints,
        assumptions: payload.assumptions,
        originalProblem: payload.originalProblem,
        normalizedProblem: payload.normalizedProblem,
        finalAnswer: buildFinalAnswer(solutionDoc),
        plots: payload.plots,
        autocorrectApplied: payload.autocorrectApplied,
        commonMistakes: payload.commonMistakes,
    });
    return [
        {
            id: "preview-page-1",
            title: "Review",
            blocks,
            elements: [],
        },
    ];
};

type SaveState = "idle" | "saving" | "saved" | "error";

export default function EditModePage() {
    const { pushToast } = useToast();
    const params = useParams();
    const router = useRouter();
    const sessionId = params?.id as string;

    const [activeTab, setActiveTab] = useState<"notes" | "edit">("edit");
    const [canonicalMarkdown, setCanonicalMarkdown] = useState("");
    const [canonicalHash, setCanonicalHash] = useState("");
    const [exportingPdf, setExportingPdf] = useState(false);
    const [exportingDocx, setExportingDocx] = useState(false);
    const [cleanPreview, setCleanPreview] = useState(true);
    const [autoWrapMath, setAutoWrapMath] = useState(true);
    const [notes, setNotes] = useState("");
    const [notesVersion, setNotesVersion] = useState(0);
    const [notesState, setNotesState] = useState<SaveState>("idle");
    const [edited, setEdited] = useState("");
    const [editVersion, setEditVersion] = useState(0);
    const [editState, setEditState] = useState<SaveState>("idle");
    const [loading, setLoading] = useState(true);
    const notesDirtyRef = useRef(false);
    const editDirtyRef = useRef(false);
    const [notesDirty, setNotesDirty] = useState(false);
    const [editDirty, setEditDirty] = useState(false);
    const insertSnippet = useCallback(
        (snippet: string) => {
            if (activeTab === "notes") {
                setNotes((prev) => `${prev}${prev.endsWith("\n") || prev.length === 0 ? "" : "\n"}${snippet}`);
                notesDirtyRef.current = true;
                setNotesDirty(true);
                setNotesState("idle");
                return;
            }
            setEdited((prev) => `${prev}${prev.endsWith("\n") || prev.length === 0 ? "" : "\n"}${snippet}`);
            editDirtyRef.current = true;
            setEditDirty(true);
            setEditState("idle");
        },
        [activeTab],
    );
    const handleImageUpload = useCallback((file: File) => {
        return new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result || ""));
            reader.onerror = () => reject(new Error("Failed to read image file"));
            reader.readAsDataURL(file);
        });
    }, []);

    const loadData = useCallback(async () => {
        const token = localStorage.getItem("token");
        if (!token) {
            router.push(`/login?redirect=/edit/${sessionId}`);
            return;
        }
        setLoading(true);
        try {
            const [canonicalRes, notesRes, editRes] = await Promise.all([
                fetch(`${API_BASE_URL}/api/v1/chat/${sessionId}/canonical_markdown`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
                fetch(`${API_BASE_URL}/api/v1/chat/${sessionId}/notes`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
                fetch(`${API_BASE_URL}/api/v1/chat/${sessionId}/edit_copy`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
            ]);

            if (!canonicalRes.ok) throw await parseApiError(canonicalRes);
            if (!notesRes.ok) throw await parseApiError(notesRes);
            if (!editRes.ok) throw await parseApiError(editRes);
            const canonicalData = await canonicalRes.json();
            const notesData = await notesRes.json();
            let editData = await editRes.json();

            if (!(editData.edited_md || "").trim()) {
                const resetRes = await fetch(`${API_BASE_URL}/api/v1/chat/${sessionId}/edit_copy/reset`, {
                    method: "POST",
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (resetRes.ok) {
                    editData = await resetRes.json();
                } else {
                    editData = { ...editData, edited_md: canonicalData.canonical_md || "" };
                }
            }

            setCanonicalMarkdown(canonicalData.canonical_md || "");
            setCanonicalHash(canonicalData.canonical_md_hash || "");
            setNotes(notesData.notes_md || "");
            setNotesVersion(Number(notesData.version || 0));
            setEdited(editData.edited_md || "");
            setEditVersion(Number(editData.version || 0));
            notesDirtyRef.current = false;
            editDirtyRef.current = false;
            setNotesDirty(false);
            setEditDirty(false);
            setNotesState("idle");
            setEditState("idle");
        } catch (error) {
            const err = error as { message?: string; requestId?: string };
            pushToast({
                type: "error",
                title: "Failed to load edit mode",
                message: err.message || "Unexpected error",
                requestId: err.requestId,
            });
        } finally {
            setLoading(false);
        }
    }, [pushToast, router, sessionId]);

    useEffect(() => {
        if (sessionId) {
            void loadData();
        }
    }, [loadData, sessionId]);

    const canExport = useMemo(() => Boolean(edited.trim()), [edited]);
    const fetchExportSolutionDoc = useCallback(async () => {
        const token = localStorage.getItem("token");
        if (!token) throw new Error("Missing auth token");
        const res = await fetch(`${API_BASE_URL}/api/v1/chat/${sessionId}/solution_doc/preview`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ markdown: edited }),
        });
        if (!res.ok) {
            const err = await parseApiError(res);
            throw err;
        }
        const data = await res.json();
        return (data.solution_doc || null) as Record<string, unknown> | null;
    }, [edited, sessionId]);


    const handleExportPdf = useCallback(async () => {
        if (exportingPdf) return;
        setExportingPdf(true);
        try {
            const exportSolutionDoc = await fetchExportSolutionDoc();
            const exportPages = buildExportPages(exportSolutionDoc);
            if (!hasExportableSolution(exportPages)) {
                throw new Error("No exportable content in review.");
            }
            const payload: SolutionExportPayload = {
                pages: exportPages,
                solveId: sessionId,
                title: "Solution Review",
                generatedAt: new Date().toISOString(),
            };
            await exportCanvasToPdf(payload);
            pushToast({ type: "success", title: "Export ready", message: "PDF generated." });
        } catch (error) {
            pushToast({
                type: "error",
                title: "Export failed",
                message: error instanceof Error ? error.message : "PDF export failed.",
            });
        } finally {
            setExportingPdf(false);
        }
    }, [exportingPdf, fetchExportSolutionDoc, pushToast, sessionId]);

    const handleExportDocx = useCallback(async () => {
        if (exportingDocx) return;
        setExportingDocx(true);
        try {
            const exportSolutionDoc = await fetchExportSolutionDoc();
            const exportPages = buildExportPages(exportSolutionDoc);
            if (!hasExportableSolution(exportPages)) {
                throw new Error("No exportable content in review.");
            }
            const payload: SolutionExportPayload = {
                pages: exportPages,
                solveId: sessionId,
                title: "Solution Review",
                generatedAt: new Date().toISOString(),
            };
            await exportCanvasToDocx(payload);
            pushToast({ type: "success", title: "Export ready", message: "DOCX generated." });
        } catch (error) {
            pushToast({
                type: "error",
                title: "Export failed",
                message: error instanceof Error ? error.message : "DOCX export failed.",
            });
        } finally {
            setExportingDocx(false);
        }
    }, [exportingDocx, fetchExportSolutionDoc, pushToast, sessionId]);

    const saveNotes = useCallback(async () => {
        const token = localStorage.getItem("token");
        if (!token) return;
        if (notesState === "saving") return;

        const bytes = new TextEncoder().encode(notes).length;
        if (bytes > MAX_CONTENT_BYTES) {
            setNotesState("error");
            pushToast({
                type: "error",
                title: "Notes too large",
                message: "Please keep notes under 50KB.",
            });
            return;
        }

        setNotesState("saving");
        try {
            const res = await fetch(`${API_BASE_URL}/api/v1/chat/${sessionId}/notes`, {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    notes_md: notes,
                    expected_version: notesVersion,
                }),
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                throw err;
            }
            const data = await res.json();
            setNotesVersion(Number(data.version || notesVersion));
            setNotesState("saved");
            notesDirtyRef.current = false;
            setNotesDirty(false);
        } catch (error) {
            const err = error as { message?: string; requestId?: string };
            setNotesState("error");
            pushToast({
                type: "error",
                title: "Failed to save notes",
                message: err.message || "Unexpected error",
                requestId: err.requestId,
            });
        }
    }, [notes, notesState, notesVersion, pushToast, sessionId]);

    const saveEdited = useCallback(async () => {
        const token = localStorage.getItem("token");
        if (!token) return;
        if (editState === "saving") return;

        const bytes = new TextEncoder().encode(edited).length;
        if (bytes > MAX_CONTENT_BYTES) {
            setEditState("error");
            pushToast({
                type: "error",
                title: "Edited copy too large",
                message: "Please keep content under 50KB.",
            });
            return;
        }

        setEditState("saving");
        try {
            const res = await fetch(`${API_BASE_URL}/api/v1/chat/${sessionId}/edit_copy`, {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    edited_md: edited,
                    expected_version: editVersion,
                }),
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                throw err;
            }
            const data = await res.json();
            setEditVersion(Number(data.version || editVersion));
            setEditState("saved");
            editDirtyRef.current = false;
            setEditDirty(false);
        } catch (error) {
            const err = error as { message?: string; requestId?: string };
            setEditState("error");
            pushToast({
                type: "error",
                title: "Failed to save edited copy",
                message: err.message || "Unexpected error",
                requestId: err.requestId,
            });
        }
    }, [editState, editVersion, edited, pushToast, sessionId]);

    const handleSave = useCallback(() => {
        if (activeTab === "notes") {
            if (notesDirtyRef.current) void saveNotes();
            return;
        }
        if (editDirtyRef.current) void saveEdited();
    }, [activeTab, saveEdited, saveNotes]);

    const saveLabel = useMemo(() => {
        const state = activeTab === "notes" ? notesState : editState;
        if (state === "saving") return "Saving...";
        if (state === "saved") return "Saved";
        if (state === "error") return "Error";
        return "Idle";
    }, [activeTab, notesState, editState]);

    const handleResetToCanonical = async () => {
        const token = localStorage.getItem("token");
        if (!token) {
            router.push(`/login?redirect=/edit/${sessionId}`);
            return;
        }
        try {
            const res = await fetch(`${API_BASE_URL}/api/v1/chat/${sessionId}/edit_copy/reset`, {
                method: "POST",
                headers: { Authorization: `Bearer ${token}` },
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                pushToast({
                    type: "error",
                    title: "Reset failed",
                    message: err.message,
                    requestId: err.requestId,
                });
                return;
            }
            const data = await res.json();
            setEdited(data.edited_md || "");
            setEditVersion(Number(data.version || editVersion));
            setCanonicalHash(data.canonical_md_hash || canonicalHash);
            setEditState("saved");
            editDirtyRef.current = false;
            pushToast({
                type: "success",
                title: "Reset complete",
                message: "Edited copy reset to canonical solution.",
            });
        } catch (error) {
            pushToast({
                type: "error",
                title: "Reset failed",
                message: error instanceof Error ? error.message : "Unexpected error",
            });
        }
    };

    return (
        <div className="min-h-screen bg-slate-50 dark:bg-slate-950 transition-colors duration-200">
            <DashboardNavBar />
            <main className="max-w-6xl mx-auto px-4 py-10">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
                    <div>
                        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Edit & Notes</h1>
                        <p className="text-sm text-slate-500 dark:text-slate-400">
                            Canonical solution is read-only. Your notes and edits are private to you.
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        <button
                            type="button"
                            onClick={() => router.push(`/chat/${sessionId}`)}
                            className="px-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-sm font-semibold text-slate-700 dark:text-slate-200"
                        >
                            Back to Chat
                        </button>
                        <div className="relative group">
                            <button
                                type="button"
                                className="px-4 py-2 rounded-lg bg-slate-900 text-white text-sm font-semibold"
                            >
                                Help
                            </button>
                            <div className="absolute right-0 mt-2 hidden group-hover:block w-72 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-lg p-3 text-xs text-slate-600 dark:text-slate-300 z-10">
                                <p className="font-semibold text-slate-900 dark:text-white mb-2">Links</p>
                                <a className="block underline" href="https://mdxeditor.dev/editor/docs/getting-started" target="_blank" rel="noreferrer">MDXEditor Getting Started</a>
                                <a className="block underline" href="https://github.com/mdx-editor/editor" target="_blank" rel="noreferrer">MDXEditor GitHub</a>
                                <a className="block underline" href="https://mdxjs.com/guides/math/" target="_blank" rel="noreferrer">MDX Math Guide</a>
                                <a className="block underline" href="https://www.markdownguide.org/basic-syntax/" target="_blank" rel="noreferrer">Markdown Syntax</a>
                                <div className="mt-3">
                                    <div className="font-semibold text-slate-900 dark:text-white">Examples</div>
                                    <div className="mt-1">Inline math: <span className="font-mono">$x^2 + 1$</span></div>
                                    <div className="mt-1">Block math:</div>
                                    <pre className="bg-slate-50 dark:bg-slate-800 p-2 rounded mt-1 whitespace-pre-wrap">{`$$
\\int_0^1 x^2 \\, dx = \\frac{1}{3}
$$`}</pre>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="flex gap-4 mb-6 items-center">
                    <button
                        type="button"
                        onClick={() => {
                            if (!edited.trim() && canonicalMarkdown) {
                                setEdited(canonicalMarkdown);
                                editDirtyRef.current = true;
                                setEditDirty(true);
                                setEditState("idle");
                            }
                            setActiveTab("edit");
                        }}
                        className={`px-4 py-2 rounded-lg text-sm font-semibold ${activeTab === "edit" ? "bg-primary text-white" : "bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200"}`}
                    >
                        My Edited Copy
                    </button>
                    <button
                        type="button"
                        onClick={() => setActiveTab("notes")}
                        className={`px-4 py-2 rounded-lg text-sm font-semibold ${activeTab === "notes" ? "bg-primary text-white" : "bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200"}`}
                    >
                        My Notes
                    </button>
                    {activeTab === "edit" && (
                        <button
                            type="button"
                            onClick={handleResetToCanonical}
                            className="px-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-sm font-semibold text-slate-700 dark:text-slate-200"
                        >
                            Reset to Canonical
                        </button>
                    )}
                    <button
                        type="button"
                        onClick={handleSave}
                        disabled={activeTab === "notes" ? !notesDirty : !editDirty}
                        className={`px-4 py-2 rounded-lg text-sm font-semibold ${
                            activeTab === "notes"
                                ? !notesDirty
                                    ? "opacity-50 cursor-not-allowed bg-slate-200 text-slate-600"
                                    : "bg-primary text-white"
                                : !editDirty
                                    ? "opacity-50 cursor-not-allowed bg-slate-200 text-slate-600"
                                    : "bg-primary text-white"
                        }`}
                    >
                        Save
                    </button>
                    <div className="ml-auto text-xs text-slate-500 dark:text-slate-400 flex items-center gap-2">
                        <span className="rounded-full w-2 h-2 bg-emerald-500" />
                        {saveLabel}
                    </div>
                </div>

                {loading ? (
                    <div className="p-10 text-center text-slate-500">Loading editor...</div>
                ) : (
                    <div className="flex flex-col gap-6">
                        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-4">
                            <MDXEditor
                                key={`${activeTab}-${notesVersion}-${editVersion}`}
                                markdown={activeTab === "notes" ? notes : edited}
                                onChange={(value) => {
                                    if (activeTab === "notes") {
                                        setNotes(value);
                                        notesDirtyRef.current = true;
                                        setNotesDirty(true);
                                        setNotesState("idle");
                                    } else {
                                        setEdited(value);
                                        editDirtyRef.current = true;
                                        setEditDirty(true);
                                        setEditState("idle");
                                    }
                                }}
                                plugins={[
                                    headingsPlugin(),
                                    listsPlugin(),
                                    linkPlugin(),
                                    linkDialogPlugin(),
                                    quotePlugin(),
                                    codeBlockPlugin(),
                                    codeMirrorPlugin(),
                                    tablePlugin(),
                                    thematicBreakPlugin(),
                                    imagePlugin({ imageUploadHandler: handleImageUpload }),
                                    markdownShortcutPlugin(),
                                    toolbarPlugin({
                                        toolbarContents: () => (
                                            <div className="flex flex-wrap items-center gap-2">
                                                <KitchenSinkToolbar />
                                                <InsertInlineMath onInsert={insertSnippet} />
                                                <InsertBlockMath onInsert={insertSnippet} />
                                            </div>
                                        ),
                                    }),
                                ]}
                                contentEditableClassName="min-h-[420px] prose prose-slate dark:prose-invert max-w-none"
                            />
                        </div>

                        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6">
                                <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                                    <div>
                                        <h3 className="text-lg font-bold text-slate-900 dark:text-white">Preview</h3>
                                    <span className="text-xs text-slate-500">Ready</span>
                                    </div>
                                <div className="flex flex-wrap items-center gap-3">
                                    <label className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
                                        <input
                                            type="checkbox"
                                            className="h-4 w-4"
                                            checked={cleanPreview}
                                            onChange={(event) => setCleanPreview(event.target.checked)}
                                        />
                                        Clean preview
                                    </label>
                                    <label className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
                                        <input
                                            type="checkbox"
                                            className="h-4 w-4"
                                            checked={autoWrapMath}
                                            onChange={(event) => setAutoWrapMath(event.target.checked)}
                                        />
                                        Auto-wrap math
                                    </label>
                                    <button
                                        type="button"
                                        onClick={() => void handleExportPdf()}
                                        disabled={!canExport || exportingPdf}
                                        className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 disabled:opacity-50"
                                    >
                                        {exportingPdf ? "Exporting..." : "Export PDF"}
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => void handleExportDocx()}
                                        disabled={!canExport || exportingDocx}
                                        className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 disabled:opacity-50"
                                    >
                                        {exportingDocx ? "Exporting..." : "Export DOCX"}
                                    </button>
                                </div>
                            </div>
                            <MarkdownPreview
                                content={activeTab === "edit" ? edited : notes}
                                cleanPreview={cleanPreview}
                                autoWrapMath={autoWrapMath}
                            />
                            {activeTab === "edit" && canonicalMarkdown && (
                                <div className="mt-6 text-xs text-slate-400">
                                    Canonical hash: {canonicalHash || "unknown"}
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}
