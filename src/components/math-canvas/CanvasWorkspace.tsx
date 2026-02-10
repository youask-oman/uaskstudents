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
  savedVersions?: SavedPaperVersion[];
  state: CanvasDocumentState;
  dispatch: React.Dispatch<DocumentAction>;
  viewMode?: "edit" | "student_report";
}

interface MathEditorTarget {
  elementId?: string;
  initialLatex: string;
}

const isInputLikeTarget = (target: EventTarget | null): boolean => {
  if (!(target instanceof HTMLElement)) return false;
  if (target.closest("input, textarea, select")) return true;
  if (target.isContentEditable) return true;
  if (target.closest("[contenteditable='true']")) return true;
  return false;
};

export default function CanvasWorkspace({
  sessionId,
  savedVersions = [],
  state,
  dispatch,
  viewMode = "edit",
}: CanvasWorkspaceProps) {
  const [latexEditorTarget, setLatexEditorTarget] = useState<MathEditorTarget | null>(null);
  const [graphEditorOpen, setGraphEditorOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [styleDraft, setStyleDraft] = useState(DEFAULT_ELEMENT_STYLE);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [savingVersion, setSavingVersion] = useState(false);
  const [exportingDocx, setExportingDocx] = useState(false);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [activeTextEditor, setActiveTextEditor] = useState<Editor | null>(null);
  const [activeTextEditorId, setActiveTextEditorId] = useState<string | null>(null);
  const versionOptions = savedVersions;
  const canUndo = state.past.length > 0;
  const canRedo = state.future.length > 0;
  const canPaste = Boolean(state.clipboard && state.clipboard.elements.length > 0);
  const hasSelection = state.selection.elementIds.length > 0;
  const canExport = useMemo(() => hasExportableSolution(state.pages), [state.pages]);

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
    [dispatch]
  );


  const handleAddPage = useCallback(() => {
    dispatch({
      type: "ADD_PAGE",
      page: {
        id: createPageId(),
        blocks: [],
        elements: [],
      },
      setActive: true,
    });
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
    if (!sessionId || sessionId === "demo-1") {
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

  return (
    <section className={styles.centerColumn}>
      {viewMode === "edit" ? (
        <>
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
          />
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

      {viewMode === "edit" && paletteOpen ? (
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
        </div>
      ) : null}

      <div className={styles.pagesStack}>
        {state.pages.map((page, index) => (
          <PaperPage
            key={page.id}
            page={page}
            index={index}
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
            onDeleteBlock={(blockId) => dispatch({ type: "DELETE_BLOCK", pageId: page.id, blockId })}
            viewMode={viewMode}
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
