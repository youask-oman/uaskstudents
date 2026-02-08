"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Editor } from "@tiptap/core";
import MathRenderer from "@/components/math/MathRendererSwitch";
import VisualRenderer from "@/components/workspace/VisualRenderer";
import RecognitionBox from "./RecognitionBox";
import RichTextElementEditor, { type RichTextCommitPayload } from "./RichTextElementEditor";
import SolutionStepsBlock from "./SolutionStepsBlock";
import { DEFAULT_ELEMENT_STYLE, createElementId } from "./documentModel";
import { CanvasBlock, CanvasElement, CanvasPageData, ToolType } from "./types";
import styles from "./MathCanvas.module.css";

interface PaperPageProps {
  page: CanvasPageData;
  index: number;
  active: boolean;
  activeTool: ToolType;
  selectedElementIds: string[];
  onActivate: () => void;
  onSelectElements: (elementIds: string[]) => void;
  onInsertElement: (element: CanvasElement) => void;
  onMoveElements: (elementIds: string[], dx: number, dy: number) => void;
  onResizeElement: (elementId: string, width: number, height: number, x?: number, y?: number) => void;
  onDeleteElements: (elementIds: string[]) => void;
  onRequestMathEdit: (elementId: string, latexRaw: string) => void;
  onCommitText: (elementId: string, payload: RichTextCommitPayload) => void;
  onActiveTextEditorChange?: (editor: Editor | null, elementId: string | null) => void;
  onUpdateBlock: (blockId: string, updater: (block: CanvasBlock) => CanvasBlock) => void;
  onDeleteBlock: (blockId: string) => void;
  exportMode?: boolean;
  viewMode?: "edit" | "student_report";
}

interface Point {
  x: number;
  y: number;
  clientX: number;
  clientY: number;
}

type DrawingType = "shape" | "compass" | "ruler";

interface DrawingDraft {
  type: DrawingType;
  start: Point;
  current: Point;
  shiftSnap: boolean;
}

interface DragDraft {
  elementIds: string[];
  startClientX: number;
  startClientY: number;
  dx: number;
  dy: number;
}

interface ResizeDraft {
  elementId: string;
  handle: "tl" | "tr" | "bl" | "br";
  startClientX: number;
  startClientY: number;
  originalWidth: number;
  originalHeight: number;
  originalX: number;
  originalY: number;
  width: number;
  height: number;
  x: number;
  y: number;
}

interface EditDraft {
  elementId: string;
}

const SAFE_PROTOCOL_RE = /^(https?:|mailto:)/i;

const sanitizeRichTextHtml = (html: string): string => {
  if (!html.trim()) return "";
  if (typeof window === "undefined") return html;
  const template = document.createElement("template");
  template.innerHTML = html;
  template.content.querySelectorAll("script, style, iframe, object, embed").forEach((node) => node.remove());
  template.content.querySelectorAll("*").forEach((node) => {
    [...node.attributes].forEach((attribute) => {
      const name = attribute.name.toLowerCase();
      if (name.startsWith("on")) node.removeAttribute(attribute.name);
    });
    if (node instanceof HTMLAnchorElement) {
      const href = node.getAttribute("href") || "";
      if (!SAFE_PROTOCOL_RE.test(href)) {
        node.removeAttribute("href");
      }
      node.setAttribute("target", "_blank");
      node.setAttribute("rel", "noopener noreferrer nofollow");
    }
  });
  return template.innerHTML;
};

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

const asPlotVisual = (title: string, xLabel: string, yLabel: string, points: Array<{ x: number; y: number }>) => {
  const xValues = points.map((point) => point.x);
  const yValues = points.map((point) => point.y);
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues);
  const yMax = Math.max(...yValues);

  return {
    title,
    axes: {
      x_label: xLabel,
      y_label: yLabel,
      y_range: [Math.floor(yMin - 1), Math.ceil(yMax + 1)],
    },
    domain: {
      x_min_latex: String(Math.floor(xMin - 1)),
      x_max_latex: String(Math.ceil(xMax + 1)),
    },
    series: [
      {
        label: title,
        points,
      },
    ],
  };
};

const snapLinePoint = (start: Point, current: Point) => {
  const dx = current.x - start.x;
  const dy = current.y - start.y;
  const angle = Math.atan2(dy, dx);
  const snappedAngle = Math.round(angle / (Math.PI / 4)) * (Math.PI / 4);
  const distance = Math.sqrt(dx * dx + dy * dy);
  return {
    x: start.x + Math.cos(snappedAngle) * distance,
    y: start.y + Math.sin(snappedAngle) * distance,
  };
};

const ResizeHandles = ({
  element,
  onResizePointerDown
}: {
  element: CanvasElement,
  onResizePointerDown: (e: React.PointerEvent, element: CanvasElement, handle: "tl" | "tr" | "bl" | "br") => void
}) => {
  return (
    <>
      <div
        key={`${element.id}-tl`}
        className={`${styles.resizeHandle} ${styles.handleTL}`}
        onPointerDown={(e) => onResizePointerDown(e, element, "tl")}
      />
      <div
        key={`${element.id}-tr`}
        className={`${styles.resizeHandle} ${styles.handleTR}`}
        onPointerDown={(e) => onResizePointerDown(e, element, "tr")}
      />
      <div
        key={`${element.id}-bl`}
        className={`${styles.resizeHandle} ${styles.handleBL}`}
        onPointerDown={(e) => onResizePointerDown(e, element, "bl")}
      />
      <div
        key={`${element.id}-br`}
        className={`${styles.resizeHandle} ${styles.handleBR}`}
        onPointerDown={(e) => onResizePointerDown(e, element, "br")}
      />
    </>
  );
};

const ElementView = React.memo(function ElementView({
  element,
  selected,
  dragPreview,
  resizePreview,
  onPointerDown,
  onDoubleClick,
  onResizePointerDown,
}: {
  element: CanvasElement;
  selected: boolean;
  dragPreview?: { dx: number; dy: number };
  resizePreview?: { width: number; height: number; x: number; y: number };
  onPointerDown: (event: React.PointerEvent, element: CanvasElement) => void;
  onDoubleClick: (element: CanvasElement) => void;
  onResizePointerDown: (event: React.PointerEvent, element: CanvasElement, handle: "tl" | "tr" | "bl" | "br") => void;
}) {
  const width = resizePreview?.width ?? element.width;
  const height = resizePreview?.height ?? element.height;
  const x = resizePreview?.x ?? element.x;
  const y = resizePreview?.y ?? element.y;

  const richTextHtml = element.type === "text" ? sanitizeRichTextHtml(element.richTextHtml || "") : "";

  const style: React.CSSProperties = {
    left: x,
    top: y,
    width,
    height,
    zIndex: element.zIndex,
    transform: dragPreview ? `translate(${dragPreview.dx}px, ${dragPreview.dy}px)` : undefined,
  };

  const strokeColor = element.style.strokeColor || DEFAULT_ELEMENT_STYLE.strokeColor;

  return (
    <div
      className={`${styles.canvasElement} ${selected ? styles.canvasElementSelected : ""}`.trim()}
      id={element.id}
      style={style}
      onPointerDown={(event) => onPointerDown(event, element)}
      onClick={(e) => e.stopPropagation()}
      onDoubleClick={() => onDoubleClick(element)}
      data-element-id={element.id}
      data-element-type={element.type}
    >
      {element.type === "text" ? (
        <div
          className={styles.textElementBody}
          style={{
            color: element.style.color,
            fontSize: typeof element.style.fontSize === "number" ? `${element.style.fontSize}px` : element.style.fontSize,
            lineHeight: 1.45,
            backgroundColor: element.style.fillColor !== "transparent" ? element.style.fillColor : undefined,
            borderColor: element.style.strokeColor,
            borderWidth: typeof element.style.strokeWidth === "number" ? `${element.style.strokeWidth}px` : element.style.strokeWidth,
            borderStyle: (element.style.strokeWidth ?? 0) > 0 ? "solid" : "none",
          }}
        >
          {richTextHtml ? (
            <div
              className={styles.richTextElementContent}
              dangerouslySetInnerHTML={{ __html: richTextHtml }}
            />
          ) : (
            element.text || "Text"
          )}
        </div>
      ) : null}

      {element.type === "math" ? (
        <div
          className={styles.mathElementBody}
          style={{
            background: element.style.fillColor !== "transparent" ? element.style.fillColor : undefined,
            borderColor: element.style.strokeColor,
            borderWidth: typeof element.style.strokeWidth === "number" ? `${element.style.strokeWidth}px` : element.style.strokeWidth,
            borderStyle: (element.style.strokeWidth ?? 0) > 0 ? "solid" : "none",
            fontSize: typeof element.style.fontSize === "number" ? `${element.style.fontSize}px` : element.style.fontSize,
          }}
        >
          <MathRenderer content={element.latexRaw} mode={element.renderMode} />
          <div className={styles.recognizedBadge}>
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>
              auto_fix_high
            </span>
            {element.badge || "AI recognized"}
          </div>
        </div>
      ) : null}

      {element.type === "shape" ? (
        <div
          className={styles.shapeElementBody}
          style={{
            background: element.style.fillColor,
            borderColor: strokeColor,
            borderWidth: typeof element.style.strokeWidth === "number" ? `${element.style.strokeWidth}px` : element.style.strokeWidth,
          }}
        />
      ) : null}

      {element.type === "line" ? (
        <svg width="100%" height="100%" className={styles.lineElementSvg}>
          <line
            x1={element.x1}
            y1={element.y1}
            x2={element.x2}
            y2={element.y2}
            stroke={strokeColor}
            strokeWidth={element.style.strokeWidth}
            strokeLinecap="round"
          />
        </svg>
      ) : null}

      {element.type === "circle" ? (
        <svg width="100%" height="100%" className={styles.lineElementSvg}>
          <circle
            cx={element.centerX}
            cy={element.centerY}
            r={element.radius}
            fill="none"
            stroke={strokeColor}
            strokeWidth={element.style.strokeWidth}
          />
        </svg>
      ) : null}

      {element.type === "plot" ? (
        <div className={styles.plotElementBody}>
          <VisualRenderer
            visual={asPlotVisual(element.title, element.xLabel, element.yLabel, element.points)}
            height={Math.max(200, Math.floor(height - 20))}
          />
        </div>
      ) : null}

      {element.type === "image" ? (
        <img
          src={element.src}
          alt={element.alt || "User image"}
          draggable={false}
          style={{ width: "100%", height: "100%", objectFit: "contain", userSelect: "none" }}
        />
      ) : null}

      {selected ? (
        <ResizeHandles element={element} onResizePointerDown={onResizePointerDown} />
      ) : null}
    </div>
  );
});

export default function PaperPage({
  page,
  index,
  active,
  activeTool,
  selectedElementIds,
  onActivate,
  onSelectElements,
  onInsertElement,
  onMoveElements,
  onResizeElement,
  onDeleteElements,
  onRequestMathEdit,
  onCommitText,
  onActiveTextEditorChange,
  onUpdateBlock,
  onDeleteBlock,
  exportMode = false,
  viewMode = "edit",
}: PaperPageProps) {
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const rafRef = useRef<number | null>(null);
  const pendingPointerRef = useRef<{ clientX: number; clientY: number; shiftKey: boolean } | null>(null);

  const drawingRef = useRef<DrawingDraft | null>(null);
  const draggingRef = useRef<DragDraft | null>(null);
  const resizingRef = useRef<ResizeDraft | null>(null);

  const [drawing, setDrawing] = useState<DrawingDraft | null>(null);
  const [dragging, setDragging] = useState<DragDraft | null>(null);
  const [resizing, setResizing] = useState<ResizeDraft | null>(null);
  const [editingText, setEditingText] = useState<EditDraft | null>(null);
  const [editingRecognition, setEditingRecognition] = useState<{ blockId: string; value: string } | null>(null);
  const [editingTextBlock, setEditingTextBlock] = useState<{ blockId: string; value: string } | null>(null);
  const readOnly = exportMode || viewMode === "student_report";

  const selectedSet = useMemo(() => new Set(selectedElementIds), [selectedElementIds]);

  const nextZIndex = useMemo(
    () => page.elements.reduce((max, element) => Math.max(max, element.zIndex), 0) + 1,
    [page.elements]
  );
  const sortedElements = useMemo(
    () => [...page.elements].sort((left, right) => left.zIndex - right.zIndex || left.createdAt - right.createdAt),
    [page.elements]
  );

  const getLocalPoint = useCallback((clientX: number, clientY: number): Point => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0, clientX, clientY };
    const bounds = canvas.getBoundingClientRect();
    return {
      x: clamp(clientX - bounds.left, 0, bounds.width),
      y: clamp(clientY - bounds.top, 0, bounds.height),
      clientX,
      clientY,
    };
  }, []);

  const clearTransientState = useCallback(() => {
    setDrawing(null);
    setDragging(null);
    setResizing(null);
  }, []);

  const queuePointerUpdate = useCallback(
    (event: PointerEvent | MouseEvent | React.PointerEvent) => {
      pendingPointerRef.current = {
        clientX: event.clientX,
        clientY: event.clientY,
        shiftKey: event.shiftKey,
      };

      if (rafRef.current !== null) return;

      rafRef.current = window.requestAnimationFrame(() => {
        rafRef.current = null;
        const latest = pendingPointerRef.current;
        if (!latest) return;

        const drawingNow = drawingRef.current;
        if (drawingNow) {
          const point = getLocalPoint(latest.clientX, latest.clientY);
          setDrawing((previous) =>
            previous
              ? {
                ...previous,
                current: point,
                shiftSnap: latest.shiftKey,
              }
              : previous
          );
        }

        const draggingNow = draggingRef.current;
        if (draggingNow) {
          const dx = latest.clientX - draggingNow.startClientX;
          const dy = latest.clientY - draggingNow.startClientY;
          setDragging((previous) =>
            previous
              ? {
                ...previous,
                dx,
                dy,
              }
              : previous
          );
        }

        const resizingNow = resizingRef.current;
        if (resizingNow) {
          const dx = latest.clientX - resizingNow.startClientX;
          const dy = latest.clientY - resizingNow.startClientY;

          setResizing((previous) => {
            if (!previous) return null;
            let { x, y, width, height } = previous;

            if (previous.handle === "br") {
              width = Math.max(40, previous.originalWidth + dx);
              height = Math.max(40, previous.originalHeight + dy);
            } else if (previous.handle === "tr") {
              width = Math.max(40, previous.originalWidth + dx);
              height = Math.max(40, previous.originalHeight - dy);
              y = previous.originalY + (previous.originalHeight - height);
            } else if (previous.handle === "bl") {
              width = Math.max(40, previous.originalWidth - dx);
              height = Math.max(40, previous.originalHeight + dy);
              x = previous.originalX + (previous.originalWidth - width);
            } else if (previous.handle === "tl") {
              width = Math.max(40, previous.originalWidth - dx);
              height = Math.max(40, previous.originalHeight - dy);
              x = previous.originalX + (previous.originalWidth - width);
              y = previous.originalY + (previous.originalHeight - height);
            }

            return { ...previous, x, y, width, height };
          });
        }
      });
    },
    [getLocalPoint]
  );

  useEffect(() => {
    drawingRef.current = drawing;
  }, [drawing]);

  useEffect(() => {
    draggingRef.current = dragging;
  }, [dragging]);

  useEffect(() => {
    resizingRef.current = resizing;
  }, [resizing]);

  const hasActiveAction = !!(drawing || dragging || resizing);

  useEffect(() => {
    if (!hasActiveAction) return;

    const onMove = (event: PointerEvent) => {
      queuePointerUpdate(event);
    };

    const onUp = (event: PointerEvent) => {
      const drawingFinal = drawingRef.current;
      const draggingFinal = draggingRef.current;
      const resizingFinal = resizingRef.current;

      if (drawingFinal) {
        const start = drawingFinal.start;
        const rawCurrent = getLocalPoint(event.clientX, event.clientY);
        const current = drawingFinal.type === "ruler" && drawingFinal.shiftSnap
          ? { ...rawCurrent, ...snapLinePoint(start, rawCurrent) }
          : rawCurrent;

        if (drawingFinal.type === "shape") {
          const x = Math.min(start.x, current.x);
          const y = Math.min(start.y, current.y);
          const width = Math.abs(current.x - start.x);
          const height = Math.abs(current.y - start.y);
          if (width >= 12 && height >= 12) {
            onInsertElement({
              id: createElementId(),
              type: "shape",
              pageId: page.id,
              x,
              y,
              width,
              height,
              zIndex: nextZIndex,
              style: { ...DEFAULT_ELEMENT_STYLE, fillColor: "#e8f2ff" },
              createdAt: Date.now(),
              updatedAt: Date.now(),
              shapeKind: "rect",
            });
          }
        } else if (drawingFinal.type === "compass") {
          const radius = Math.max(12, Math.hypot(current.x - start.x, current.y - start.y));
          onInsertElement({
            id: createElementId(),
            type: "circle",
            pageId: page.id,
            x: start.x - radius,
            y: start.y - radius,
            width: radius * 2,
            height: radius * 2,
            zIndex: nextZIndex,
            style: { ...DEFAULT_ELEMENT_STYLE, fillColor: "transparent" },
            createdAt: Date.now(),
            updatedAt: Date.now(),
            radius,
            centerX: radius,
            centerY: radius,
          });
        } else if (drawingFinal.type === "ruler") {
          const x2y2 = drawingFinal.shiftSnap ? snapLinePoint(start, current) : { x: current.x, y: current.y };
          const x = Math.min(start.x, x2y2.x);
          const y = Math.min(start.y, x2y2.y);
          const width = Math.max(1, Math.abs(x2y2.x - start.x));
          const height = Math.max(1, Math.abs(x2y2.y - start.y));
          const x1Local = start.x - x;
          const y1Local = start.y - y;
          const x2Local = x2y2.x - x;
          const y2Local = x2y2.y - y;

          onInsertElement({
            id: createElementId(),
            type: "line",
            pageId: page.id,
            x,
            y,
            width,
            height,
            zIndex: nextZIndex,
            style: { ...DEFAULT_ELEMENT_STYLE, fillColor: "transparent" },
            createdAt: Date.now(),
            updatedAt: Date.now(),
            x1: x1Local,
            y1: y1Local,
            x2: x2Local,
            y2: y2Local,
            length: Math.hypot(x2y2.x - start.x, x2y2.y - start.y),
          });
        }
      }

      if (draggingFinal) {
        const dx = Math.round(draggingFinal.dx);
        const dy = Math.round(draggingFinal.dy);
        if (Math.abs(dx) > 0 || Math.abs(dy) > 0) {
          onMoveElements(draggingFinal.elementIds, dx, dy);
        }
      }

      if (resizingFinal) {
        onResizeElement(resizingFinal.elementId, resizingFinal.width, resizingFinal.height, resizingFinal.x, resizingFinal.y);
      }

      clearTransientState();
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);

    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [
    hasActiveAction,
    getLocalPoint,
    onInsertElement,
    onMoveElements,
    onResizeElement,
    page.id,
    nextZIndex,
    queuePointerUpdate,
    clearTransientState
  ]);

  const onCanvasPointerDown = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    if (readOnly) return;
    if (typeof event.button === "number" && event.button !== 0) return;
    onActivate();

    const point = getLocalPoint(event.clientX, event.clientY);

    if (activeTool === "text") {
      const id = createElementId();
      onInsertElement({
        id,
        type: "text",
        pageId: page.id,
        x: point.x,
        y: point.y,
        width: 280,
        height: 80,
        zIndex: nextZIndex,
        style: { ...DEFAULT_ELEMENT_STYLE, fillColor: "transparent" },
        createdAt: Date.now(),
        updatedAt: Date.now(),
        text: "Double-click to edit",
      });
      onSelectElements([id]);
      return;
    }

    if (["shape", "compass", "ruler"].includes(activeTool as string)) {
      setDrawing({
        type: activeTool as DrawingType,
        start: point,
        current: point,
        shiftSnap: event.shiftKey,
      });
      return;
    }

    if (activeTool !== "palette") {
      onSelectElements([]);
      setEditingText(null);
    }
  }, [activeTool, getLocalPoint, nextZIndex, onActivate, onInsertElement, onSelectElements, page.id, readOnly]);

  const onElementPointerDown = useCallback((event: React.PointerEvent, element: CanvasElement) => {
    if (readOnly) return;
    if (typeof event.button === "number" && event.button !== 0) return;
    event.stopPropagation();
    onActivate();

    if (activeTool === "eraser") {
      onDeleteElements([element.id]);
      return;
    }

    const currentSelection = new Set(selectedElementIds);
    if (event.shiftKey) {
      if (currentSelection.has(element.id)) {
        currentSelection.delete(element.id);
      } else {
        currentSelection.add(element.id);
      }
    } else {
      currentSelection.clear();
      currentSelection.add(element.id);
    }

    const nextSelection = Array.from(currentSelection);
    onSelectElements(nextSelection);

    if (["shape", "compass", "ruler"].includes(activeTool as string)) {
      return;
    }

    if (activeTool === "text" && element.type === "text") {
      onSelectElements([element.id]);
      setEditingText({ elementId: element.id });
      return;
    }

    setDragging({
      elementIds: nextSelection.length > 0 ? nextSelection : [element.id],
      startClientX: event.clientX,
      startClientY: event.clientY,
      dx: 0,
      dy: 0,
    });
  }, [activeTool, onActivate, onDeleteElements, onSelectElements, readOnly, selectedElementIds]);

  const onResizePointerDown = useCallback((
    event: React.PointerEvent,
    element: CanvasElement,
    handle: "tl" | "tr" | "bl" | "br"
  ) => {
    if (readOnly) return;
    event.preventDefault();
    event.stopPropagation();

    // Explicitly set capture on the handle
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);

    setResizing({
      elementId: element.id,
      handle,
      startClientX: event.clientX,
      startClientY: event.clientY,
      originalWidth: element.width,
      originalHeight: element.height,
      originalX: element.x,
      originalY: element.y,
      width: element.width,
      height: element.height,
      x: element.x,
      y: element.y,
    });
  }, [readOnly]);

  const onElementDoubleClick = useCallback((element: CanvasElement) => {
    if (readOnly) return;
    if (element.type === "text") {
      setEditingText({ elementId: element.id });
      return;
    }
    if (element.type === "math") {
      onRequestMathEdit(element.id, element.latexRaw);
    }
  }, [onRequestMathEdit, readOnly]);

  const editingElement = useMemo(() => {
    if (!editingText) return null;
    return (page.elements.find(e => e.id === editingText.elementId && e.type === "text") as Extract<CanvasElement, { type: "text" }>) || null;
  }, [editingText, page.elements]);

  const getCursorClass = () => {
    if (activeTool === "eraser") return styles.cursorEraser;
    if (activeTool === "text") return styles.cursorText;
    if (["shape", "compass", "ruler", "graph"].includes(activeTool as string)) return styles.cursorCrosshair;
    return "";
  };

  return (
    <article
      className={`paper ${styles.paperPage} ${active ? styles.paperPageActive : ""} ${getCursorClass()}`.trim()}
      onClick={onActivate}
    >
      <div className={styles.paperPageHeader}>
        <span className={styles.paperPageTitle}>
          Page {index + 1}
          {page.title ? ` - ${page.title}` : ""}
        </span>
      </div>

      {page.blocks && page.blocks.length > 0 ? (
        <div className={styles.paperBlocksStack}>
          {page.blocks.map((block) => {
            if (block.type === "recognition") {
              return (
                <div key={block.id} id={block.id} className={styles.paperBlockWrap}>
                  {!exportMode && viewMode === "edit" ? (
                    <div className={styles.paperBlockActions} data-no-export="true">
                      <button
                        type="button"
                        className={styles.blockActionButton}
                        onClick={() => setEditingRecognition({ blockId: block.id, value: block.latex })}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className={styles.blockActionButton}
                        onClick={() => onDeleteBlock(block.id)}
                      >
                        Delete
                      </button>
                    </div>
                  ) : null}
                  {editingRecognition?.blockId === block.id ? (
                    <div className={styles.inlineEditWrap}>
                      <textarea
                        className={styles.inlineEditTextArea}
                        value={editingRecognition.value}
                        onChange={(event) =>
                          setEditingRecognition((prev) =>
                            prev ? { ...prev, value: event.target.value } : prev
                          )
                        }
                      />
                      <div className={styles.blockActions}>
                        <button
                          type="button"
                          className={styles.blockActionButton}
                          onClick={() => {
                            onUpdateBlock(block.id, (current) =>
                              current.type === "recognition"
                                ? { ...current, latex: editingRecognition.value.trim() || current.latex }
                                : current
                            );
                            setEditingRecognition(null);
                          }}
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          className={styles.blockActionButton}
                          onClick={() => setEditingRecognition(null)}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <RecognitionBox latex={block.latex} exportMode={exportMode} />
                  )}
                </div>
              );
            }
            if (block.type === "steps") {
              return (
                <div key={block.id} id={block.id} className={styles.paperBlockWrap}>
                  {!exportMode && viewMode === "edit" ? (
                    <div className={styles.paperBlockActions} data-no-export="true">
                      <button
                        type="button"
                        className={styles.blockActionButton}
                        onClick={() => onDeleteBlock(block.id)}
                      >
                        Delete
                      </button>
                    </div>
                  ) : null}
                  <SolutionStepsBlock
                    steps={block.steps}
                    result={block.result}
                    finalAnswer={block.finalAnswer}
                    verificationChecks={block.verificationChecks}
                    domainConstraints={block.domainConstraints}
                    assumptions={block.assumptions}
                    originalProblem={block.originalProblem}
                    normalizedProblem={block.normalizedProblem}
                    commonMistakes={block.commonMistakes}
                    autocorrectApplied={block.autocorrectApplied}
                    sectionId={block.id}
                    exportMode={exportMode}
                    editable={viewMode === "edit"}
                    onActiveTextEditorChange={onActiveTextEditorChange}
                    onChange={(next) =>
                      onUpdateBlock(block.id, (current) =>
                        current.type === "steps" ? { ...current, ...next } : current
                      )
                    }
                  />
                </div>
              );
            }
            if (block.type === "text") {
              return (
                <div key={block.id} id={block.id} className={styles.paperBlockWrap}>
                  {!exportMode && viewMode === "edit" ? (
                    <div className={styles.paperBlockActions} data-no-export="true">
                      <button
                        type="button"
                        className={styles.blockActionButton}
                        onClick={() => setEditingTextBlock({ blockId: block.id, value: block.text })}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className={styles.blockActionButton}
                        onClick={() => onDeleteBlock(block.id)}
                      >
                        Delete
                      </button>
                    </div>
                  ) : null}
                  {editingTextBlock?.blockId === block.id && viewMode === "edit" ? (
                    <div className={styles.inlineEditWrap}>
                      <textarea
                        className={styles.inlineEditTextArea}
                        value={editingTextBlock.value}
                        onChange={(event) =>
                          setEditingTextBlock((prev) =>
                            prev ? { ...prev, value: event.target.value } : prev
                          )
                        }
                      />
                      <div className={styles.blockActions}>
                        <button
                          type="button"
                          className={styles.blockActionButton}
                          onClick={() => {
                            onUpdateBlock(block.id, (current) =>
                              current.type === "text"
                                ? { ...current, text: editingTextBlock.value.trim() || current.text }
                                : current
                            );
                            setEditingTextBlock(null);
                          }}
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          className={styles.blockActionButton}
                          onClick={() => setEditingTextBlock(null)}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className={styles.paperTextBlock}>{block.text}</div>
                  )}
                </div>
              );
            }
            return null;
          })}
        </div>
      ) : null}

      <div
        className={styles.paperCanvas}
        ref={canvasRef}
        onPointerDown={onCanvasPointerDown}
        style={{ minHeight: page.elements.length > 0 ? "800px" : "400px" }}
      >
        {sortedElements.map((element) => {
          const selected = selectedSet.has(element.id);
          const dragPreview = dragging && dragging.elementIds.includes(element.id) ? { dx: dragging.dx, dy: dragging.dy } : undefined;
          const resizePreview =
            resizing && resizing.elementId === element.id
              ? { width: resizing.width, height: resizing.height, x: resizing.x, y: resizing.y }
              : undefined;

          return (
            <ElementView
              key={element.id}
              element={element}
              selected={selected}
              dragPreview={dragPreview}
              resizePreview={resizePreview}
              onPointerDown={onElementPointerDown}
              onDoubleClick={onElementDoubleClick}
              onResizePointerDown={onResizePointerDown}
            />
          );
        })}

        {drawing ? (
          <div className={styles.canvasDraft}>
            {drawing.type === "shape" ? (
              <div
                className={styles.draftRect}
                style={{
                  left: Math.min(drawing.start.x, drawing.current.x),
                  top: Math.min(drawing.start.y, drawing.current.y),
                  width: Math.abs(drawing.current.x - drawing.start.x),
                  height: Math.abs(drawing.current.y - drawing.start.y),
                }}
              />
            ) : null}

            {drawing.type === "compass" ? (
              <svg className={styles.draftSvg}>
                <circle
                  cx={drawing.start.x}
                  cy={drawing.start.y}
                  r={Math.hypot(drawing.current.x - drawing.start.x, drawing.current.y - drawing.start.y)}
                  fill="rgba(74, 144, 226, 0.15)"
                  stroke="var(--primary-color)"
                  strokeWidth="2"
                  strokeDasharray="4 4"
                />
              </svg>
            ) : null}

            {drawing.type === "ruler" ? (
              <svg className={styles.draftSvg}>
                <line
                  x1={drawing.start.x}
                  y1={drawing.start.y}
                  x2={drawing.shiftSnap ? snapLinePoint(drawing.start, drawing.current).x : drawing.current.x}
                  y2={drawing.shiftSnap ? snapLinePoint(drawing.start, drawing.current).y : drawing.current.y}
                  stroke="var(--primary-color)"
                  strokeWidth="2"
                  strokeDasharray="4 4"
                />
              </svg>
            ) : null}
          </div>
        ) : null}

        {editingElement && editingText ? (
          <div
            className={styles.canvasTextEditor}
            style={{
              left: editingElement.x,
              top: editingElement.y,
              width: editingElement.width,
              height: editingElement.height,
            }}
            onPointerDown={(e) => e.stopPropagation()}
          >
            <RichTextElementEditor
              elementId={editingElement.id}
              initialText={editingElement.text || ""}
              initialHtml={editingElement.richTextHtml}
              initialJson={editingElement.richTextJson}
              onActivate={onActiveTextEditorChange || (() => { })}
              onCommit={(payload) => onCommitText(editingElement.id, payload)}
              onRequestClose={() => setEditingText(null)}
            />
          </div>
        ) : null}
      </div>
    </article>
  );
}
