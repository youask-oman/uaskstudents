"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import EditorToolbar from "./EditorToolbar";
import GraphEditor from "./GraphEditor";
import LatexEditor from "./LatexEditor";
import PaperPage from "./PaperPage";
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

export default function CanvasWorkspace({ sessionId, savedVersions = [], state, dispatch }: CanvasWorkspaceProps) {
  const [latexEditorTarget, setLatexEditorTarget] = useState<MathEditorTarget | null>(null);
  const [graphEditorOpen, setGraphEditorOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [styleDraft, setStyleDraft] = useState(DEFAULT_ELEMENT_STYLE);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [savingVersion, setSavingVersion] = useState(false);
  const [versionOptions, setVersionOptions] = useState<SavedPaperVersion[]>(savedVersions);
  const [selectedVersionKey, setSelectedVersionKey] = useState<string>(savedVersions[0]?.key || "");

  const activePage = useMemo(
    () => state.pages.find((page) => page.id === state.activePageId) ?? state.pages[0],
    [state.activePageId, state.pages]
  );
  const selectedVersion = useMemo(
    () => versionOptions.find((version) => version.key === selectedVersionKey) || null,
    [selectedVersionKey, versionOptions]
  );

  useEffect(() => {
    setVersionOptions(savedVersions);
    setSelectedVersionKey(savedVersions[0]?.key || "");
  }, [savedVersions]);

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
      const response = await fetch(`/api/v1/sessions/${sessionId}/paper-versions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: `Canvas Version ${new Date().toISOString()}`,
          pages: state.pages,
        }),
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({} as Record<string, unknown>));
        const detail = typeof error?.detail === "string" ? error.detail : "Failed to save version.";
        throw new Error(detail);
      }
      const payload = (await response.json()) as { version?: number };
      const versionNum = Number(payload.version);
      const savedAt = typeof (payload as Record<string, unknown>).saved_at === "string"
        ? String((payload as Record<string, unknown>).saved_at)
        : new Date().toISOString();
      const titleRaw = typeof (payload as Record<string, unknown>).title === "string"
        ? String((payload as Record<string, unknown>).title)
        : "";
      const version = Number.isFinite(versionNum) && versionNum > 0 ? versionNum : versionOptions.length + 1;
      const title = titleRaw.trim() || `Version ${version}`;
      const pagesSnapshot = JSON.parse(JSON.stringify(state.pages)) as SavedPaperVersion["pages"];
      const nextVersion: SavedPaperVersion = {
        key: `${version}-${savedAt || Date.now()}`,
        version,
        title,
        savedAt,
        pages: pagesSnapshot,
      };
      setVersionOptions((prev) => {
        const deduped = prev.filter((entry) => entry.version !== nextVersion.version);
        return [nextVersion, ...deduped].sort((left, right) => right.version - left.version);
      });
      setSelectedVersionKey(nextVersion.key);
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
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
      if (isInputLikeTarget(event.target)) return;

      const key = event.key.toLowerCase();

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
  }, [activePage, dispatch, state.activePageId]);

  useEffect(() => {
    const onDelete = (event: KeyboardEvent) => {
      if (event.key !== "Delete" && event.key !== "Backspace") return;
      if (isInputLikeTarget(event.target)) return;
      if (state.selection.elementIds.length === 0) return;
      event.preventDefault();
      dispatch({ type: "DELETE_ELEMENTS", elementIds: state.selection.elementIds });
    };
    window.addEventListener("keydown", onDelete);
    return () => window.removeEventListener("keydown", onDelete);
  }, [dispatch, state.selection.elementIds]);

  const canUndo = state.past.length > 0;
  const canRedo = state.future.length > 0;
  const canPaste = Boolean(state.clipboard && state.clipboard.elements.length > 0);
  const hasSelection = state.selection.elementIds.length > 0;

  return (
    <section className={styles.centerColumn}>
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
        onAddPage={handleAddPage}
        onSaveVersion={handleSaveVersion}
        savingVersion={savingVersion}
      />

      {saveMessage ? <div className={styles.versionSaveNotice}>{saveMessage}</div> : null}

      {versionOptions.length > 0 ? (
        <div className={styles.versionLoadPanel}>
          <span className={styles.versionLoadLabel}>Saved versions</span>
          <select
            className={styles.versionLoadSelect}
            value={selectedVersionKey}
            onChange={(event) => setSelectedVersionKey(event.target.value)}
          >
            {versionOptions.map((version) => {
              const savedAtLabel = version.savedAt ? new Date(version.savedAt).toLocaleString() : "";
              return (
                <option key={version.key} value={version.key}>
                  {`v${version.version} - ${version.title}${savedAtLabel ? ` (${savedAtLabel})` : ""}`}
                </option>
              );
            })}
          </select>
          <button
            type="button"
            className={styles.versionLoadButton}
            disabled={!selectedVersion}
            onClick={handleLoadVersion}
          >
            Load
          </button>
        </div>
      ) : null}

      {paletteOpen ? (
        <div className={styles.palettePanel} role="region" aria-label="Style palette">
          <label className={styles.paletteControl}>
            <span>Text</span>
            <input
              type="color"
              value={styleDraft.color}
              aria-label="Text color"
              onChange={(event) => setStyleDraft((prev) => ({ ...prev, color: event.target.value }))}
            />
          </label>
          <label className={styles.paletteControl}>
            <span>Stroke</span>
            <input
              type="color"
              value={styleDraft.strokeColor}
              aria-label="Stroke color"
              onChange={(event) => setStyleDraft((prev) => ({ ...prev, strokeColor: event.target.value }))}
            />
          </label>
          <label className={styles.paletteControl}>
            <span>Fill</span>
            <input
              type="color"
              value={styleDraft.fillColor}
              aria-label="Fill color"
              onChange={(event) => setStyleDraft((prev) => ({ ...prev, fillColor: event.target.value }))}
            />
          </label>
          <label className={styles.paletteRange}>
            <span>Stroke width</span>
            <input
              type="range"
              min={1}
              max={8}
              step={1}
              value={styleDraft.strokeWidth}
              onChange={(event) => setStyleDraft((prev) => ({ ...prev, strokeWidth: Number(event.target.value) }))}
            />
          </label>
          <label className={styles.paletteRange}>
            <span>Font size</span>
            <input
              type="range"
              min={12}
              max={36}
              step={1}
              value={styleDraft.fontSize}
              onChange={(event) => setStyleDraft((prev) => ({ ...prev, fontSize: Number(event.target.value) }))}
            />
          </label>
          <button
            type="button"
            className={`${styles.headerButton} ${styles.headerButtonPrimary}`}
            disabled={!hasSelection}
            onClick={() => {
              dispatch({
                type: "APPLY_STYLE",
                elementIds: state.selection.elementIds,
                style: {
                  color: styleDraft.color,
                  strokeColor: styleDraft.strokeColor,
                  fillColor: styleDraft.fillColor,
                  strokeWidth: styleDraft.strokeWidth,
                  fontSize: styleDraft.fontSize,
                },
              });
            }}
          >
            Apply to Selection
          </button>
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
            onCommitText={(elementId, text) => dispatch({ type: "SET_TEXT_CONTENT", elementId, text })}
            onUpdateBlock={(blockId, updater) => dispatch({ type: "UPDATE_BLOCK", pageId: page.id, blockId, updater })}
            onDeleteBlock={(blockId) => dispatch({ type: "DELETE_BLOCK", pageId: page.id, blockId })}
          />
        ))}
      </div>

      {latexEditorTarget ? (
        <LatexEditor
          initialValue={latexEditorTarget.initialLatex}
          onClose={() => setLatexEditorTarget(null)}
          onInsert={handleInsertMath}
        />
      ) : null}

      {graphEditorOpen ? <GraphEditor onClose={() => setGraphEditorOpen(false)} onInsert={handleInsertPlot} /> : null}
    </section>
  );
}
