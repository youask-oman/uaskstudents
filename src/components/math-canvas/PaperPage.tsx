"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import MathRenderer from "@/components/math/MathRendererSwitch";
import VisualRenderer from "@/components/workspace/VisualRenderer";
import RecognitionBox from "./RecognitionBox";
import SolutionStepsBlock from "./SolutionStepsBlock";
import { DEFAULT_ELEMENT_STYLE, createElementId } from "./documentModel";
import { CanvasElement, CanvasPageData, ToolType } from "./types";
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
  onCommitText: (elementId: string, text: string) => void;
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
  startClientX: number;
  startClientY: number;
  originalWidth: number;
  originalHeight: number;
  originalX: number;
  originalY: number;
  width: number;
  height: number;
}

interface EditDraft {
  elementId: string;
  value: string;
}

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
  resizePreview?: { width: number; height: number };
  onPointerDown: (event: React.PointerEvent, element: CanvasElement) => void;
  onDoubleClick: (element: CanvasElement) => void;
  onResizePointerDown: (event: React.PointerEvent, element: CanvasElement) => void;
}) {
  const width = resizePreview?.width ?? element.width;
  const height = resizePreview?.height ?? element.height;

  const style: React.CSSProperties = {
    left: element.x,
    top: element.y,
    width,
    height,
    zIndex: element.zIndex,
    transform: dragPreview ? `translate(${dragPreview.dx}px, ${dragPreview.dy}px)` : undefined,
  };

  const strokeColor = element.style.strokeColor || DEFAULT_ELEMENT_STYLE.strokeColor;

  return (
    <div
      className={`${styles.canvasElement} ${selected ? styles.canvasElementSelected : ""}`.trim()}
      style={style}
      onPointerDown={(event) => onPointerDown(event, element)}
      onMouseDown={(event) => onPointerDown(event as unknown as React.PointerEvent, element)}
      onDoubleClick={() => onDoubleClick(element)}
      data-element-id={element.id}
      data-element-type={element.type}
    >
      {element.type === "text" ? (
        <div
          className={styles.textElementBody}
          style={{ color: element.style.color, fontSize: element.style.fontSize, lineHeight: 1.45 }}
        >
          {element.text || "Text"}
        </div>
      ) : null}

      {element.type === "math" ? (
        <div className={styles.mathElementBody}>
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
            borderWidth: element.style.strokeWidth,
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

      {selected && element.type !== "line" && element.type !== "circle" ? (
        <button
          type="button"
          className={styles.resizeHandle}
          aria-label="Resize element"
          onPointerDown={(event) => onResizePointerDown(event, element)}
          onMouseDown={(event) => onResizePointerDown(event as unknown as React.PointerEvent, element)}
        />
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

  const selectedSet = useMemo(() => new Set(selectedElementIds), [selectedElementIds]);

  const nextZIndex = useMemo(
    () => page.elements.reduce((max, element) => Math.max(max, element.zIndex), 0) + 1,
    [page.elements]
  );
  const sortedElements = useMemo(
    () => [...page.elements].sort((left, right) => left.zIndex - right.zIndex || left.createdAt - right.createdAt),
    [page.elements]
  );

  const getLocalPoint = (clientX: number, clientY: number): Point => {
    const canvas = canvasRef.current;
    const safeClientX = Number.isFinite(clientX) ? clientX : 0;
    const safeClientY = Number.isFinite(clientY) ? clientY : 0;
    if (!canvas) {
      return { x: 0, y: 0, clientX: safeClientX, clientY: safeClientY };
    }
    const bounds = canvas.getBoundingClientRect();
    return {
      x: clamp(safeClientX - bounds.left, 0, bounds.width),
      y: clamp(safeClientY - bounds.top, 0, bounds.height),
      clientX: safeClientX,
      clientY: safeClientY,
    };
  };

  const clearTransientState = () => {
    setDrawing(null);
    setDragging(null);
    setResizing(null);
  };

  const queuePointerUpdate = useCallback(
    (event: PointerEvent | MouseEvent) => {
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
          setResizing((previous) =>
            previous
              ? {
                  ...previous,
                  width: Math.max(40, Math.round(previous.originalWidth + dx)),
                  height: Math.max(40, Math.round(previous.originalHeight + dy)),
                }
              : previous
          );
        }
      });
    },
    []
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

  useEffect(() => {
    if (!drawing && !dragging && !resizing) return;

    const onMove = (event: PointerEvent | MouseEvent) => {
      queuePointerUpdate(event);
    };

    const onUp = (event: PointerEvent | MouseEvent) => {
      if (drawing) {
        const start = drawing.start;
        const rawCurrent = getLocalPoint(event.clientX, event.clientY);
        const current = drawing.type === "ruler" && drawing.shiftSnap
          ? { ...rawCurrent, ...snapLinePoint(start, rawCurrent) }
          : rawCurrent;

        if (drawing.type === "shape") {
          const x = Math.min(start.x, current.x);
          const y = Math.min(start.y, current.y);
          const width = Math.abs(current.x - start.x);
          const height = Math.abs(current.y - start.y);
          if (width >= 12 && height >= 12) {
            const now = Date.now();
            onInsertElement({
              id: createElementId(),
              type: "shape",
              pageId: page.id,
              x,
              y,
              width,
              height,
              zIndex: nextZIndex,
              style: {
                ...DEFAULT_ELEMENT_STYLE,
                fillColor: "#e8f2ff",
              },
              createdAt: now,
              updatedAt: now,
              shapeKind: "rect",
            });
          }
        }

        if (drawing.type === "compass") {
          const radius = Math.max(12, Math.hypot(current.x - start.x, current.y - start.y));
          const now = Date.now();
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
            createdAt: now,
            updatedAt: now,
            radius,
            centerX: radius,
            centerY: radius,
          });
        }

        if (drawing.type === "ruler") {
          const x2y2 = drawing.shiftSnap ? snapLinePoint(start, current) : { x: current.x, y: current.y };
          const x = Math.min(start.x, x2y2.x);
          const y = Math.min(start.y, x2y2.y);
          const width = Math.max(1, Math.abs(x2y2.x - start.x));
          const height = Math.max(1, Math.abs(x2y2.y - start.y));
          const now = Date.now();
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
            createdAt: now,
            updatedAt: now,
            x1: x1Local,
            y1: y1Local,
            x2: x2Local,
            y2: y2Local,
            length: Math.hypot(x2y2.x - start.x, x2y2.y - start.y),
          });
        }
      }

      if (dragging) {
        const dx = Math.round(dragging.dx);
        const dy = Math.round(dragging.dy);
        if (Math.abs(dx) > 0 || Math.abs(dy) > 0) {
          onMoveElements(dragging.elementIds, dx, dy);
        }
      }

      if (resizing) {
        onResizeElement(resizing.elementId, resizing.width, resizing.height, resizing.originalX, resizing.originalY);
      }

      clearTransientState();
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);

    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [
    drawing,
    dragging,
    nextZIndex,
    onInsertElement,
    onMoveElements,
    onResizeElement,
    page.id,
    queuePointerUpdate,
    resizing,
  ]);

  useEffect(() => {
    return () => {
      if (rafRef.current !== null) {
        window.cancelAnimationFrame(rafRef.current);
      }
    };
  }, []);

  const onCanvasPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (typeof event.button === "number" && event.button !== 0) return;
    onActivate();

    const point = getLocalPoint(event.clientX, event.clientY);

    if (activeTool === "text") {
      const id = createElementId();
      const now = Date.now();
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
        createdAt: now,
        updatedAt: now,
        text: "Double-click to edit",
      });
      onSelectElements([id]);
      setEditingText({ elementId: id, value: "Double-click to edit" });
      return;
    }

    if (activeTool === "shape" || activeTool === "compass" || activeTool === "ruler") {
      setDrawing({
        type: activeTool,
        start: point,
        current: point,
        shiftSnap: event.shiftKey,
      });
      return;
    }

    if (activeTool !== "palette") {
      onSelectElements([]);
    }
  };

  const onElementPointerDown = (event: React.PointerEvent, element: CanvasElement) => {
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

    if (activeTool === "shape" || activeTool === "compass" || activeTool === "ruler") {
      return;
    }

    setDragging({
      elementIds: nextSelection.length > 0 ? nextSelection : [element.id],
      startClientX: event.clientX,
      startClientY: event.clientY,
      dx: 0,
      dy: 0,
    });
  };

  const onResizePointerDown = (event: React.PointerEvent, element: CanvasElement) => {
    event.preventDefault();
    event.stopPropagation();

    setResizing({
      elementId: element.id,
      startClientX: event.clientX,
      startClientY: event.clientY,
      originalWidth: element.width,
      originalHeight: element.height,
      originalX: element.x,
      originalY: element.y,
      width: element.width,
      height: element.height,
    });
  };

  const onElementDoubleClick = (element: CanvasElement) => {
    if (element.type === "text") {
      setEditingText({ elementId: element.id, value: element.text });
      return;
    }
    if (element.type === "math") {
      onRequestMathEdit(element.id, element.latexRaw);
    }
  };

  const editingElement = useMemo(
    () => (editingText ? page.elements.find((element) => element.id === editingText.elementId && element.type === "text") : null),
    [editingText, page.elements]
  );

  return (
    <article className={`${styles.paperPage} ${active ? styles.paperPageActive : ""}`.trim()} onClick={onActivate}>
      <div className={styles.paperPageHeader}>
        <span className={styles.paperPageTitle}>Page {index + 1}</span>
      </div>

      {page.blocks && page.blocks.length > 0 ? (
        <div className={styles.paperBlocksStack}>
          {page.blocks.map((block) => {
            if (block.type === "recognition") {
              return <RecognitionBox key={block.id} latex={block.latex} />;
            }
            if (block.type === "steps") {
              return <SolutionStepsBlock key={block.id} steps={block.steps} result={block.result} />;
            }
            return (
              <div key={block.id} style={{ fontSize: 14, color: "var(--text-main)" }}>
                <MathRenderer content={block.text} mode="prose" />
              </div>
            );
          })}
        </div>
      ) : null}

      <div
        className={styles.paperCanvas}
        ref={canvasRef}
        onPointerDown={onCanvasPointerDown}
        onMouseDown={(event) => onCanvasPointerDown(event as unknown as React.PointerEvent<HTMLDivElement>)}
        data-testid={`paper-canvas-${page.id}`}
      >
        {page.elements.length === 0 ? (
          <div className={styles.paperCanvasHint}>Blank page. Use the toolbar to add math blocks.</div>
        ) : null}

        {sortedElements.map((element) => {
          const selected = selectedSet.has(element.id);
          const dragPreview = dragging && dragging.elementIds.includes(element.id) ? { dx: dragging.dx, dy: dragging.dy } : undefined;
          const resizePreview = resizing && resizing.elementId === element.id ? { width: resizing.width, height: resizing.height } : undefined;

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

            {drawing.type === "ruler" ? (
              <svg className={styles.draftSvg}>
                {(() => {
                  const snapped = drawing.shiftSnap
                    ? snapLinePoint(drawing.start, drawing.current)
                    : { x: drawing.current.x, y: drawing.current.y };
                  return (
                    <line
                      x1={drawing.start.x}
                      y1={drawing.start.y}
                      x2={snapped.x}
                      y2={snapped.y}
                      stroke="var(--primary-color)"
                      strokeWidth={2}
                      strokeDasharray="5 4"
                    />
                  );
                })()}
              </svg>
            ) : null}

            {drawing.type === "compass" ? (
              <svg className={styles.draftSvg}>
                <circle
                  cx={drawing.start.x}
                  cy={drawing.start.y}
                  r={Math.max(8, Math.hypot(drawing.current.x - drawing.start.x, drawing.current.y - drawing.start.y))}
                  fill="none"
                  stroke="var(--primary-color)"
                  strokeWidth={2}
                  strokeDasharray="5 4"
                />
              </svg>
            ) : null}
          </div>
        ) : null}

        {editingElement && editingText ? (
          <textarea
            className={styles.canvasTextEditor}
            style={{
              left: editingElement.x,
              top: editingElement.y,
              width: editingElement.width,
              height: editingElement.height,
              fontSize: editingElement.style.fontSize,
              color: editingElement.style.color,
            }}
            value={editingText.value}
            autoFocus
            onChange={(event) => setEditingText({ elementId: editingText.elementId, value: event.target.value })}
            onBlur={() => {
              onCommitText(editingText.elementId, editingText.value.trim());
              setEditingText(null);
            }}
            onKeyDown={(event) => {
              if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "enter") {
                event.preventDefault();
                onCommitText(editingText.elementId, editingText.value.trim());
                setEditingText(null);
              }
              if (event.key === "Escape") {
                event.preventDefault();
                setEditingText(null);
              }
            }}
          />
        ) : null}
      </div>
    </article>
  );
}
