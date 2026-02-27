"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Editor } from "@tiptap/core";
import EditorToolbar from "./EditorToolbar";
import GraphEditor from "./GraphEditor";
import LatexEditor from "./LatexEditor";
import PaperPage from "./PaperPage";
import RichTextToolbar from "./RichTextToolbar";
import {
  exportCanvasToDocx,
  exportCanvasToPdf,
  hasExportableSolution,
  SolutionExportPayload,
} from "./export/exportDocument";
import {
  DEFAULT_ELEMENT_STYLE,
  DocumentAction,
  buildInitialDocumentState,
  createElementId,
  createPageId,
} from "./documentModel";
import { CanvasDocumentState, CanvasElement, SavedPaperVersion, ToolType } from "./types";
import styles from "./MathCanvas.module.css";

interface CanvasWorkspaceProps {
  sessionId: string;
  attemptId?: string | null;
  solveTier?: string | null;
  onOpenShare?: () => void;
  savedVersions?: SavedPaperVersion[];
  state: CanvasDocumentState;
  dispatch: React.Dispatch<DocumentAction>;
  viewMode?: "edit" | "student_report";
  hideStepLabels?: boolean;
  paperVariant?: "default" | "final_handwritten" | "short_paper";
}

interface MathEditorTarget {
  elementId?: string;
  initialLatex: string;
}

type PaperTone = "white" | "cream" | "sage" | "sky";
type PaperTexture = "blank" | "lined" | "dot";
type FinalHandFont = "kalam" | "architect" | "gochi" | "inter" | "arial" | "georgia" | "times";
const PRIMARY_TOOLS = new Set<ToolType>(["text", "math", "shape", "compass", "ruler", "graph", "eraser", "palette"]);

const isInputLikeTarget = (target: EventTarget | null): boolean => {
  if (!(target instanceof HTMLElement)) return false;
  if (target.closest("input, textarea, select")) return true;
  if (target.isContentEditable) return true;
  if (target.closest("[contenteditable='true']")) return true;
  return false;
};

export default function CanvasWorkspace({
  sessionId,
  attemptId,
  solveTier,
  onOpenShare,
  savedVersions = [],
  state,
  dispatch,
  viewMode = "edit",
  hideStepLabels = false,
  paperVariant = "default",
}: CanvasWorkspaceProps) {
  const [latexEditorTarget, setLatexEditorTarget] = useState<MathEditorTarget | null>(null);
  const [graphEditorOpen, setGraphEditorOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [styleDraft, setStyleDraft] = useState(DEFAULT_ELEMENT_STYLE);
  const [paperTone, setPaperTone] = useState<PaperTone>("cream");
  const [paperTexture, setPaperTexture] = useState<PaperTexture>("lined");
  const [finalHandFont, setFinalHandFont] = useState<FinalHandFont>("kalam");
  const [finalHandFontSize, setFinalHandFontSize] = useState<number>(15);
  const [newPageId, setNewPageId] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [savingVersion, setSavingVersion] = useState(false);
  const [exportingDocx, setExportingDocx] = useState(false);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [activeTextEditor, setActiveTextEditor] = useState<Editor | null>(null);
  const [activeTextEditorId, setActiveTextEditorId] = useState<string | null>(null);
  const [richTextPaletteColor, setRichTextPaletteColor] = useState("#1e293b");
  const versionOptions = savedVersions;
  const canUndo = state.past.length > 0;
  const canRedo = state.future.length > 0;
  const canPaste = Boolean(state.clipboard && state.clipboard.elements.length > 0);
  const hasSelection = state.selection.elementIds.length > 0;
  const canExport = useMemo(() => hasExportableSolution(state.pages), [state.pages]);
  const richTextPaletteMode = Boolean(activeTextEditor && activeTextEditor.isEditable);
  const normalizedTier = String(solveTier || "").trim().toUpperCase();
  const isFinalTier = normalizedTier === "FINAL";
  const isShortTier = normalizedTier === "SHORT" || normalizedTier === "SHORT_STEPS";
  const hideToolbarForTier = isFinalTier;
  const disablePrimaryTools = false;
  const showPaperSettingsButton = isFinalTier || isShortTier;

  const [selectedVersionKey, setSelectedVersionKey] = useState<string>(() => savedVersions[0]?.key ?? "");

  useEffect(() => {
    if (hasSelection) {
      const firstId = state.selection.elementIds[0];
      const element = state.pages.flatMap((p) => p.elements).find((e) => e.id === firstId);
      if (element) {
        setStyleDraft(element.style);
      }
    }
  }, [state.selection.elementIds, state.pages, hasSelection]);

  const updateDraftAndApply = useCallback(
    (updater: (prev: typeof styleDraft) => typeof styleDraft) => {
      setStyleDraft((prev) => {
        const next = updater(prev);
        if (state.selection.elementIds.length > 0) {
          // Defer dispatch to avoid the "Cannot update a component while rendering a different component" error.
          // This happens because dispatch triggers a state update in the parent (ChatPage) while 
          // CanvasWorkspace is still processing its own state update.
          setTimeout(() => {
            dispatch({
              type: "APPLY_STYLE",
              elementIds: state.selection.elementIds,
              style: next,
            });
          }, 0);
        }
        return next;
      });
    },
    [dispatch, state.selection.elementIds]
  );

  const activePage = useMemo(
    () => state.pages.find((page) => page.id === state.activePageId) ?? state.pages[0],
    [state.activePageId, state.pages]
  );
  const selectedVersion = useMemo(
    () => versionOptions.find((version) => version.key === selectedVersionKey) || null,
    [selectedVersionKey, versionOptions]
  );

  useEffect(() => {
    if (!selectedVersionKey || !savedVersions.some((version) => version.key === selectedVersionKey)) {
      setSelectedVersionKey(savedVersions[0]?.key ?? "");
    }
  }, [savedVersions, selectedVersionKey]);

  const handleSelectTool = useCallback(
    (tool: ToolType) => {
      if (hideToolbarForTier && PRIMARY_TOOLS.has(tool)) {
        dispatch({ type: "SET_TOOL", tool: "none" });
        setPaletteOpen(false);
        return;
      }
      dispatch({ type: "SET_TOOL", tool });
      if (tool === "math") {
        setLatexEditorTarget({ initialLatex: "" });
      }
      if (tool === "graph") {
        setGraphEditorOpen(true);
      }
      if (tool === "palette") {
        setPaletteOpen((prev) => !prev);
        return;
      }
      setPaletteOpen(false);
    },
    [hideToolbarForTier, dispatch]
  );

  useEffect(() => {
    if (!hideToolbarForTier) return;
    if (!PRIMARY_TOOLS.has(state.activeTool)) return;
    dispatch({ type: "SET_TOOL", tool: "none" });
    setPaletteOpen(false);
  }, [hideToolbarForTier, state.activeTool, dispatch]);


  const handleAddPage = useCallback(() => {
    const pageId = createPageId();
    dispatch({
      type: "ADD_PAGE",
      page: {
        id: pageId,
        blocks: [],
        elements: [],
      },
      setActive: true,
    });
    setNewPageId(pageId);
    window.setTimeout(() => {
      setNewPageId((current) => (current === pageId ? null : current));
    }, 420);
  }, [dispatch]);

  const handleDeletePage = useCallback(() => {
    if (state.pages.length <= 1) return;
    dispatch({ type: "DELETE_PAGE", pageId: state.activePageId });
  }, [dispatch, state.pages.length, state.activePageId]);

  const handleInsertMath = useCallback(
    (latex: string) => {
      if (!activePage) return;
      const trimmed = latex.trim();
      if (!trimmed) return;

      if (latexEditorTarget?.elementId) {
        dispatch({
          type: "SET_MATH_LATEX",
          elementId: latexEditorTarget.elementId,
          latexRaw: trimmed,
        });
        return;
      }

      const now = Date.now();
      const element: CanvasElement = {
        id: createElementId(),
        type: "math",
        pageId: activePage.id,
        x: 120,
        y: 120,
        width: 560,
        height: 140,
        zIndex: activePage.elements.length + 1,
        style: { ...DEFAULT_ELEMENT_STYLE, fillColor: "#f0f7ff" },
        createdAt: now,
        updatedAt: now,
        latexRaw: trimmed,
        renderMode: "block",
        badge: "AI recognized",
      };

      dispatch({
        type: "INSERT_ELEMENT",
        pageId: activePage.id,
        element,
      });
    },
    [activePage, dispatch, latexEditorTarget]
  );

  const handleInsertPlot = useCallback(
    (payload: {
      title: string;
      xLabel: string;
      yLabel: string;
      points: Array<{ x: number; y: number }>;
    }) => {
      if (!activePage) return;
      const now = Date.now();
      const element: CanvasElement = {
        id: createElementId(),
        type: "plot",
        pageId: activePage.id,
        x: 120,
        y: 300,
        width: 560,
        height: 280,
        zIndex: activePage.elements.length + 1,
        style: { ...DEFAULT_ELEMENT_STYLE, fillColor: "#ffffff" },
        createdAt: now,
        updatedAt: now,
        title: payload.title,
        xLabel: payload.xLabel,
        yLabel: payload.yLabel,
        points: payload.points,
      };
      dispatch({ type: "INSERT_ELEMENT", pageId: activePage.id, element });
    },
    [activePage, dispatch]
  );

  const handleCopy = useCallback(() => {
    dispatch({ type: "COPY_SELECTION" });
  }, [dispatch]);

  const handleCut = useCallback(() => {
    dispatch({ type: "CUT_SELECTION" });
  }, [dispatch]);

  const handlePaste = useCallback(() => {
    dispatch({ type: "PASTE_CLIPBOARD", targetPageId: state.activePageId });
  }, [dispatch, state.activePageId]);

  const handleSaveVersion = useCallback(async () => {
    if (!sessionId || sessionId.startsWith("demo")) {
      setSaveMessage("Version saving is unavailable in demo mode.");
      return;
    }
    if (savingVersion) return;
    setSavingVersion(true);
    setSaveMessage(null);
    try {
      const versionCount = versionOptions.length;
      const newTitle = `${sessionId}_V${versionCount + 1}`;

      const response = await fetch(`/api/v1/sessions/${sessionId}/paper-versions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: newTitle,
          pages: state.pages,
        }),
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({} as Record<string, unknown>));
        const detail = typeof error?.detail === "string" ? error.detail : "Failed to save version.";
        throw new Error(detail);
      }
      const payload = (await response.json()) as { version?: number };
      setSaveMessage(`Saved version ${payload.version ?? ""}`.trim());
    } catch (error) {
      console.error("Failed to save paper version", error);
      setSaveMessage("Failed to save version.");
    } finally {
      setSavingVersion(false);
    }
  }, [savingVersion, sessionId, state.pages, versionOptions.length]);

  const handleLoadVersion = useCallback(() => {
    if (!selectedVersion) return;
    dispatch({
      type: "RESET",
      state: buildInitialDocumentState(selectedVersion.pages, state.activeTool),
    });
    setSaveMessage(`Loaded ${selectedVersion.title}`);
  }, [dispatch, selectedVersion, state.activeTool]);

  useEffect(() => {
    if (viewMode === "student_report") return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
      if (isInputLikeTarget(event.target)) return;

      const key = event.key.toLowerCase();

      if (key === "escape") {
        event.preventDefault();
        if (state.activeTool !== "none") {
          dispatch({ type: "SET_TOOL", tool: "none" });
        } else if (state.selection.elementIds.length > 0) {
          dispatch({ type: "SELECT_ELEMENTS", elementIds: [] });
        }
        return;
      }

      if (key === "z" && event.shiftKey) {
        event.preventDefault();
        dispatch({ type: "REDO" });
        return;
      }

      if (key === "z") {
        event.preventDefault();
        dispatch({ type: "UNDO" });
        return;
      }

      if (key === "y") {
        event.preventDefault();
        dispatch({ type: "REDO" });
        return;
      }

      if (key === "c") {
        event.preventDefault();
        dispatch({ type: "COPY_SELECTION" });
        return;
      }

      if (key === "x") {
        event.preventDefault();
        dispatch({ type: "CUT_SELECTION" });
        return;
      }

      if (key === "v") {
        event.preventDefault();
        dispatch({ type: "PASTE_CLIPBOARD", targetPageId: state.activePageId });
        return;
      }

      if (key === "a" && activePage) {
        event.preventDefault();
        dispatch({
          type: "SELECT_ELEMENTS",
          elementIds: activePage.elements.map((element) => element.id),
        });
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activePage, dispatch, state.activePageId, state.activeTool, state.selection.elementIds.length, viewMode]);

  useEffect(() => {
    if (viewMode === "student_report") return;
    const onDelete = (event: KeyboardEvent) => {
      if (event.key !== "Delete" && event.key !== "Backspace") return;
      if (isInputLikeTarget(event.target)) return;
      if (state.selection.elementIds.length === 0) return;
      event.preventDefault();
      dispatch({ type: "DELETE_ELEMENTS", elementIds: state.selection.elementIds });
    };
    window.addEventListener("keydown", onDelete);
    return () => window.removeEventListener("keydown", onDelete);
  }, [dispatch, state.selection.elementIds, viewMode]);


  const buildExportPayload = useCallback((): SolutionExportPayload => {
    const tier =
      typeof window !== "undefined" ? (window.localStorage.getItem("selected_solve_tier") || undefined) : undefined;
    return {
      pages: state.pages,
      solveId: sessionId,
      tier: tier ? tier.toUpperCase() : undefined,
      title: "Solution",
      generatedAt: new Date().toISOString(),
    };
  }, [sessionId, state.pages]);

  const handleExportPdf = useCallback(async () => {
    if (exportingPdf) return;
    setExportingPdf(true);
    try {
      await exportCanvasToPdf(buildExportPayload());
      setSaveMessage("PDF export generated.");
    } catch (error) {
      console.error("Failed to export PDF", error);
      setSaveMessage(error instanceof Error ? error.message : "Failed to export PDF.");
    } finally {
      setExportingPdf(false);
    }
  }, [buildExportPayload, exportingPdf]);

  const handleExportDocx = useCallback(async () => {
    if (exportingDocx) return;
    setExportingDocx(true);
    try {
      await exportCanvasToDocx(buildExportPayload());
      setSaveMessage("DOCX export generated.");
    } catch (error) {
      console.error("Failed to export DOCX", error);
      setSaveMessage(error instanceof Error ? error.message : "Failed to export DOCX.");
    } finally {
      setExportingDocx(false);
    }
  }, [buildExportPayload, exportingDocx]);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleInsertImage = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      const src = e.target?.result as string;
      if (src) {
        const id = createElementId();
        dispatch({
          type: "INSERT_ELEMENT",
          pageId: state.activePageId,
          element: {
            id,
            type: "image",
            pageId: state.activePageId,
            x: 100,
            y: 100,
            width: 300,
            height: 200,
            zIndex: (state.pages.find((p) => p.id === state.activePageId)?.elements.length || 10) + 1,
            style: { ...DEFAULT_ELEMENT_STYLE, strokeWidth: 0, fillColor: "transparent" },
            createdAt: Date.now(),
            updatedAt: Date.now(),
            src,
            alt: file.name,
          } as CanvasElement,
          select: true,
        });
      }
    };
    reader.readAsDataURL(file);
    event.target.value = "";
  }, [dispatch, state.activePageId, state.pages]);

  const handleActiveTextEditorChange = useCallback((editor: Editor | null, elementId: string | null) => {
    setActiveTextEditor(editor);
    setActiveTextEditorId(elementId);
    if (editor && elementId) {
      // If a text editor is active, we might want to sync style?
    }
  }, []);

  useEffect(() => {
    if (!activeTextEditor) return;
    const attrs = activeTextEditor.getAttributes("textStyle") as { color?: string };
    const next = typeof attrs?.color === "string" && attrs.color.trim() ? attrs.color.trim() : "#1e293b";
    setRichTextPaletteColor(next);
  }, [activeTextEditor, activeTextEditorId]);

  const applyRichTextColor = useCallback((color: string) => {
    if (!activeTextEditor || !activeTextEditor.isEditable) return;
    const next = color.trim();
    if (!next) return;
    const ok = activeTextEditor.chain().focus().setColor(next).run();
    if (ok) setRichTextPaletteColor(next);
  }, [activeTextEditor]);

  const paperToneClass = useMemo(() => {
    if (paperTone === "white") return styles.paperToneWhite;
    if (paperTone === "sage") return styles.paperToneSage;
    if (paperTone === "sky") return styles.paperToneSky;
    return styles.paperToneCream;
  }, [paperTone]);

  const paperTextureClass = useMemo(() => {
    if (paperTexture === "blank") return styles.paperTextureBlank;
    if (paperTexture === "dot") return styles.paperTextureDot;
    return styles.paperTextureLined;
  }, [paperTexture]);

  const finalHandFontFamily = useMemo(() => {
    if (finalHandFont === "architect") return '"Architects Daughter", "Kalam", "Gochi Hand", cursive';
    if (finalHandFont === "gochi") return '"Gochi Hand", "Kalam", "Architects Daughter", cursive';
    if (finalHandFont === "arial") return 'Arial, Helvetica, sans-serif';
    if (finalHandFont === "georgia") return 'Georgia, "Times New Roman", serif';
    if (finalHandFont === "times") return '"Times New Roman", Times, serif';
    if (finalHandFont === "inter") return '"Inter", -apple-system, sans-serif';
    return '"Kalam", "Architects Daughter", "Gochi Hand", cursive';
  }, [finalHandFont]);

  const paperTypographyStyle = useMemo<React.CSSProperties | undefined>(() => {
    if (paperVariant !== "final_handwritten" && paperVariant !== "short_paper") return undefined;
    return {
      ["--final-hand-font-family" as string]: finalHandFontFamily,
      ["--final-hand-font-size" as string]: `${finalHandFontSize}px`,
      ["--final-hand-result-font-size" as string]: `${finalHandFontSize}px`,
      ["--short-paper-font-family" as string]: finalHandFontFamily,
      ["--short-paper-font-size" as string]: `${finalHandFontSize}px`,
    };
  }, [paperVariant, finalHandFontFamily, finalHandFontSize]);

  return (
    <section className={`${styles.centerColumn} ${paperTextureClass} ${paperVariant === "final_handwritten" ? styles.centerColumnFinalHandwritten : ""} ${paperVariant === "short_paper" ? styles.centerColumnShortPaper : ""}`.trim()}>
      {viewMode === "edit" ? (
        <>
          {!hideToolbarForTier ? (
            <EditorToolbar
              activeTool={state.activeTool}
              canUndo={canUndo}
              canRedo={canRedo}
              canPaste={canPaste}
              hasSelection={hasSelection}
              paletteOpen={paletteOpen}
              onSelectTool={handleSelectTool}
              onUndo={() => dispatch({ type: "UNDO" })}
              onRedo={() => dispatch({ type: "REDO" })}
              onCut={handleCut}
              onCopy={handleCopy}
              onPaste={handlePaste}
              activeEditor={activeTextEditor}
              onNotice={(message) => setSaveMessage(message)}
              onInsertImage={handleInsertImage}
              disablePrimaryTools={disablePrimaryTools}
            />
          ) : null}
          {showPaperSettingsButton ? (
            <div className={styles.toolbar} style={{ minHeight: "auto", paddingTop: 0 }}>
              <div className={styles.toolbarActionsRight}>
                <button
                  type="button"
                  className={styles.secondaryActionButton}
                  onClick={() => setPaletteOpen((prev) => !prev)}
                >
                  Paper settings
                </button>
              </div>
            </div>
          ) : null}
          {paletteOpen ? (
            <div className={styles.paperSettingsPopover} role="dialog" aria-label="Paper settings">
              <div className={styles.paperSettingsGrid}>
                <div className={styles.paperSettingsColumnLeft}>
                  <div className={styles.paperSettingsSection}>
                    <span className={styles.paperSettingsLabel}>Paper Color</span>
                    <div className={styles.paperToneRow}>
                      {[
                        { key: "white", color: "#FFFFFF", label: "White" },
                        { key: "cream", color: "#FFFDF5", label: "Cream" },
                        { key: "sage", color: "#F0F4F1", label: "Sage" },
                        { key: "sky", color: "#F0F7FF", label: "Sky" },
                      ].map((tone) => (
                        <button
                          key={tone.key}
                          type="button"
                          className={`${styles.paperToneDot} ${paperTone === tone.key ? styles.paperToneDotActive : ""}`.trim()}
                          style={{ backgroundColor: tone.color }}
                          onClick={() => setPaperTone(tone.key as PaperTone)}
                          aria-label={`Set ${tone.label} paper color`}
                        />
                      ))}
                    </div>
                  </div>
                  <div className={styles.paperSettingsSection}>
                    <span className={styles.paperSettingsLabel}>Texture</span>
                    <div className={styles.paperTextureRow}>
                      {[
                        { key: "blank", label: "Blank" },
                        { key: "lined", label: "Lined" },
                        { key: "dot", label: "Dot Grid" },
                      ].map((texture) => (
                        <button
                          key={texture.key}
                          type="button"
                          className={`${styles.paperTextureChip} ${paperTexture === texture.key ? styles.paperTextureChipActive : ""}`.trim()}
                          onClick={() => setPaperTexture(texture.key as PaperTexture)}
                          aria-label={`Set ${texture.label} paper texture`}
                        >
                          {texture.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
                <div className={styles.paperSettingsColumnRight}>
                  {paperVariant === "final_handwritten" || paperVariant === "short_paper" ? (
                    <>
                      <div className={styles.paperSettingsSection}>
                        <span className={styles.paperSettingsLabel}>Font</span>
                        <select
                          className={styles.paperSelect}
                          value={finalHandFont}
                          onChange={(e) => setFinalHandFont(e.target.value as FinalHandFont)}
                          aria-label="Set handwritten font"
                        >
                          <option value="kalam">Kalam</option>
                          <option value="architect">Architects Daughter</option>
                          <option value="gochi">Gochi Hand</option>
                          <option value="inter">Inter</option>
                          <option value="arial">Arial</option>
                          <option value="georgia">Georgia</option>
                          <option value="times">Times New Roman</option>
                        </select>
                      </div>
                      <div className={styles.paperSettingsSection}>
                        <span className={styles.paperSettingsLabel}>Font Size</span>
                        <div className={styles.paperRangeRow}>
                          <input
                            type="range"
                            min={12}
                            max={48}
                            step={1}
                            value={finalHandFontSize}
                            onChange={(e) => setFinalHandFontSize(Number(e.target.value))}
                            aria-label="Set paper font size"
                          />
                          <span className={styles.paperRangeValue}>{finalHandFontSize}px</span>
                        </div>
                      </div>
                    </>
                  ) : null}
                </div>
              </div>
            </div>
          ) : null}
          <RichTextToolbar
            key={activeTextEditorId || "no-active-editor"}
            canExport={canExport}
            exportingDocx={exportingDocx}
            exportingPdf={exportingPdf}
            savingVersion={savingVersion}
            onExportPdf={handleExportPdf}
            onExportDocx={handleExportDocx}
            onSaveVersion={handleSaveVersion}
            onAddPage={handleAddPage}
            onDeletePage={handleDeletePage}
            canDeletePage={state.pages.length > 1 && state.activePageId !== state.pages[0].id}
            canShare={Boolean(onOpenShare)}
            onShare={() => onOpenShare?.()}
            versionOptions={versionOptions}
            selectedVersionKey={selectedVersionKey}
            setSelectedVersionKey={setSelectedVersionKey}
            handleLoadVersion={handleLoadVersion}
            selectedVersion={selectedVersion}
          />
        </>
      ) : (
        <div className={styles.toolbar}>
          <div className={styles.toolbarActionsRight}>
            <button type="button" className={styles.secondaryActionButton} disabled={!canExport || exportingPdf} onClick={() => void handleExportPdf()}>
              {exportingPdf ? "Exporting..." : "Export PDF"}
            </button>
            <button
              type="button"
              className={styles.secondaryActionButton}
              disabled={!canExport || exportingDocx}
              onClick={() => void handleExportDocx()}
            >
              {exportingDocx ? "Exporting..." : "Export DOCX"}
            </button>
          </div>
        </div>
      )}

      {saveMessage ? <div className={styles.versionSaveNotice}>{saveMessage}</div> : null}

      {false && viewMode === "edit" && paletteOpen ? (
        <div
          className={styles.palettePanel}
          role="region"
          aria-label="Style palette"
          onMouseDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            className={styles.paletteClose}
            onClick={() => setPaletteOpen(false)}
            aria-label="Close style palette"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
          {richTextPaletteMode ? (
            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "20px" }}>
              <div className={styles.colorGridRow}>
                <span className={styles.colorGridLabel}>
                  <span className="material-symbols-outlined" style={{ fontSize: 14 }}>format_color_text</span>
                  Text Color
                </span>
                <div className={styles.colorGrid}>
                  {["#111827", "#ef4444", "#f97316", "#eab308", "#22c55e", "#3b82f6", "#6366f1", "#a855f7", "#ec4899", "#64748b"].map((c) => (
                    <button
                      key={c}
                      type="button"
                      className={`${styles.colorSwatch} ${richTextPaletteColor === c ? styles.colorSwatchActive : ""}`}
                      style={{ backgroundColor: c }}
                      onClick={() => applyRichTextColor(c)}
                      title={c}
                    />
                  ))}
                  <input
                    type="color"
                    className={styles.customColorInput}
                    value={richTextPaletteColor}
                    onChange={(e) => applyRichTextColor(e.target.value)}
                    title="Custom color"
                  />
                </div>
              </div>
            </div>
          ) : (
          <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "20px" }}>
            <div className={styles.colorGridRow}>
              <span className={styles.colorGridLabel}>
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>format_color_text</span>
                Text
              </span>
              <div className={styles.colorGrid}>
                {["#000000", "#ffffff", "#64748b", "#ef4444", "#f97316", "#eab308", "#22c55e", "#3b82f6", "#6366f1", "#a855f7"].map((c) => (
                  <button
                    key={c}
                    type="button"
                    className={`${styles.colorSwatch} ${styleDraft.color === c ? styles.colorSwatchActive : ""}`}
                    style={{ backgroundColor: c }}
                    onClick={() => updateDraftAndApply((prev) => ({ ...prev, color: c }))}
                    title={c}
                  />
                ))}
                <input
                  type="color"
                  className={styles.customColorInput}
                  value={styleDraft.color}
                  onChange={(e) => updateDraftAndApply((prev) => ({ ...prev, color: e.target.value }))}
                  title="Custom color"
                />
              </div>
            </div>

            <div className={styles.colorGridRow}>
              <span className={styles.colorGridLabel}>
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>border_color</span>
                Stroke
              </span>
              <div className={styles.colorGrid}>
                {["#000000", "#ffffff", "#475569", "#dc2626", "#ea580c", "#ca8a04", "#16a34a", "#2563eb", "#4f46e5", "#9333ea"].map((c) => (
                  <button
                    key={c}
                    type="button"
                    className={`${styles.colorSwatch} ${styleDraft.strokeColor === c ? styles.colorSwatchActive : ""}`}
                    style={{ backgroundColor: c }}
                    onClick={() => updateDraftAndApply((prev) => ({ ...prev, strokeColor: c }))}
                    title={c}
                  />
                ))}
                <input
                  type="color"
                  className={styles.customColorInput}
                  value={styleDraft.strokeColor}
                  onChange={(e) => updateDraftAndApply((prev) => ({ ...prev, strokeColor: e.target.value }))}
                  title="Custom color"
                />
              </div>
            </div>

            <div className={styles.colorGridRow}>
              <span className={styles.colorGridLabel}>
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>format_color_fill</span>
                Fill
              </span>
              <div className={styles.colorGrid}>
                {["transparent", "#ffffff", "#f1f5f9", "#fee2e2", "#ffedd5", "#fef9c3", "#dcfce7", "#dbeafe", "#e0e7ff", "#f3e8ff"].map((c) => (
                  <button
                    key={c}
                    type="button"
                    className={`${styles.colorSwatch} ${styleDraft.fillColor === c ? styles.colorSwatchActive : ""}`}
                    style={{
                      backgroundColor: c === "transparent" ? "white" : c,
                      backgroundImage: c === "transparent" ? "linear-gradient(45deg, #ccc 25%, transparent 25%, transparent 75%, #ccc 75%, #ccc), linear-gradient(45deg, #ccc 25%, transparent 25%, transparent 75%, #ccc 75%, #ccc)" : "none",
                      backgroundSize: c === "transparent" ? "8px 8px" : "auto",
                      backgroundPosition: c === "transparent" ? "0 0, 4px 4px" : "0 0"
                    }}
                    onClick={() => updateDraftAndApply((prev) => ({ ...prev, fillColor: c }))}
                    title={c === "transparent" ? "No fill" : c}
                  />
                ))}
                <input
                  type="color"
                  className={styles.customColorInput}
                  value={styleDraft.fillColor === "transparent" ? "#ffffff" : styleDraft.fillColor}
                  onChange={(e) => updateDraftAndApply((prev) => ({ ...prev, fillColor: e.target.value }))}
                  title="Custom color"
                />
              </div>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", borderTop: "1px solid var(--divider-color)", paddingTop: "20px" }}>
            <label className={styles.paletteRange}>
              <span className={styles.colorGridLabel}>
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>line_weight</span>
                Stroke width
              </span>
              <input
                type="range"
                min={0}
                max={12}
                step={1}
                value={styleDraft.strokeWidth}
                onChange={(event) => updateDraftAndApply((prev) => ({ ...prev, strokeWidth: Number(event.target.value) }))}
              />
            </label>
            <label className={styles.paletteRange}>
              <span className={styles.colorGridLabel}>
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>format_size</span>
                Font size
              </span>
              <input
                type="range"
                min={8}
                max={72}
                step={1}
                value={styleDraft.fontSize}
                onChange={(event) => updateDraftAndApply((prev) => ({ ...prev, fontSize: Number(event.target.value) }))}
              />
            </label>
          </div>
          </>
          )}

          {!richTextPaletteMode ? (
          <div style={{ borderTop: "1px solid var(--divider-color)", paddingTop: "16px", display: "flex", justifyContent: "flex-end" }}>
            <button
              type="button"
              className={`${styles.headerButton} ${styles.headerButtonPrimary}`}
              onClick={() => {
                dispatch({
                  type: "APPLY_STYLE",
                  elementIds: state.selection.elementIds,
                  style: styleDraft,
                });
                setPaletteOpen(false);
              }}
            >
              Apply to Selection
            </button>
          </div>
          ) : null}
        </div>
      ) : null}

      <div
        className={`${styles.pagesStack} ${paperToneClass} ${paperVariant === "final_handwritten" ? styles.pagesStackFinalHandwritten : ""} ${paperVariant === "short_paper" ? styles.pagesStackShortPaper : ""}`.trim()}
        style={paperTypographyStyle}
      >
        {state.pages.map((page) => (
          <PaperPage
            key={page.id}
            page={page}
            attemptId={attemptId}
            active={page.id === state.activePageId}
            activeTool={state.activeTool}
            selectedElementIds={page.id === state.activePageId ? state.selection.elementIds : []}
            onActivate={() => dispatch({ type: "SET_ACTIVE_PAGE", pageId: page.id })}
            onSelectElements={(elementIds) => dispatch({ type: "SELECT_ELEMENTS", elementIds })}
            onInsertElement={(element) => dispatch({ type: "INSERT_ELEMENT", pageId: page.id, element })}
            onMoveElements={(elementIds, dx, dy) => dispatch({ type: "MOVE_ELEMENTS", elementIds, dx, dy })}
            onResizeElement={(elementId, width, height, x, y) =>
              dispatch({ type: "RESIZE_ELEMENT", elementId, width, height, x, y })
            }
            onDeleteElements={(elementIds) => dispatch({ type: "DELETE_ELEMENTS", elementIds })}
            onRequestMathEdit={(elementId, latexRaw) => {
              setLatexEditorTarget({ elementId, initialLatex: latexRaw });
              dispatch({ type: "SET_TOOL", tool: "math" });
            }}
            onCommitText={(elementId, payload) =>
              dispatch({
                type: "SET_TEXT_CONTENT",
                elementId,
                text: payload.text,
                richTextHtml: payload.richTextHtml,
                richTextJson: payload.richTextJson,
              })
            }
            onActiveTextEditorChange={handleActiveTextEditorChange}
            onUpdateBlock={(blockId, updater) => dispatch({ type: "UPDATE_BLOCK", pageId: page.id, blockId, updater })}
            onDeleteBlock={(blockId) => {
              const firstPageId = state.pages[0]?.id;
              if (firstPageId && page.id === firstPageId) return;
              dispatch({ type: "DELETE_BLOCK", pageId: page.id, blockId });
            }}
            isFirstPage={page.id === state.pages[0]?.id}
            viewMode={viewMode}
            isNew={page.id === newPageId}
            hideStepLabels={hideStepLabels}
            finalHandwritten={paperVariant === "final_handwritten"}
            shortPaper={paperVariant === "short_paper"}
          />
        ))}
      </div>

      {
        viewMode === "edit" && latexEditorTarget ? (
          <LatexEditor
            initialValue={latexEditorTarget.initialLatex}
            onClose={() => {
              setLatexEditorTarget(null);
              dispatch({ type: "SET_TOOL", tool: "none" });
            }}
            onInsert={handleInsertMath}
          />
        ) : null
      }

      {
        viewMode === "edit" && graphEditorOpen ? (
          <GraphEditor
            onClose={() => {
              setGraphEditorOpen(false);
              dispatch({ type: "SET_TOOL", tool: "none" });
            }}
            onInsert={handleInsertPlot}
          />
        ) : null
      }

      {
        viewMode === "edit" ? (
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept="image/*"
            style={{ display: "none" }}
            aria-hidden="true"
          />
        ) : null
      }
    </section >
  );
}
