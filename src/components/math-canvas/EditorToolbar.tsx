"use client";

import React from "react";
import { ToolType } from "./types";
import styles from "./MathCanvas.module.css";

interface EditorToolbarProps {
  activeTool: ToolType;
  canUndo: boolean;
  canRedo: boolean;
  canPaste: boolean;
  hasSelection: boolean;
  paletteOpen: boolean;
  onSelectTool: (tool: ToolType) => void;
  onUndo: () => void;
  onRedo: () => void;
  onCut: () => void;
  onCopy: () => void;
  onPaste: () => void;
  onAddPage: () => void;
}

const toolButtons: Array<{ tool: ToolType; icon: string; label: string; accent?: boolean }> = [
  { tool: "text", icon: "title", label: "Text" },
  { tool: "math", icon: "functions", label: "Equation (LaTeX)", accent: true },
  { tool: "shape", icon: "crop_square", label: "Block / Highlight" },
  { tool: "compass", icon: "explore", label: "Compass (Circle/Arc)", accent: true },
  { tool: "ruler", icon: "straighten", label: "Ruler (Line/Measure)" },
  { tool: "graph", icon: "show_chart", label: "Plot Graph", accent: true },
  { tool: "eraser", icon: "ink_eraser", label: "Eraser" },
  { tool: "palette", icon: "palette", label: "Colors / Style", accent: true },
];

interface IconButtonProps {
  icon: string;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  active?: boolean;
  accent?: boolean;
  extraClassName?: string;
}

function IconButton({
  icon,
  label,
  onClick,
  disabled,
  active,
  accent,
  extraClassName,
}: IconButtonProps) {
  return (
    <button
      type="button"
      className={`${styles.toolButton} ${active ? styles.toolButtonActive : ""} ${extraClassName || ""}`.trim()}
      title={label}
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
    >
      <span
        className={`material-symbols-outlined ${accent ? styles.toolAccent : ""}`}
        style={{ fontSize: 20 }}
        aria-hidden="true"
      >
        {icon}
      </span>
    </button>
  );
}

export default function EditorToolbar({
  activeTool,
  canUndo,
  canRedo,
  canPaste,
  hasSelection,
  paletteOpen,
  onSelectTool,
  onUndo,
  onRedo,
  onCut,
  onCopy,
  onPaste,
  onAddPage,
}: EditorToolbarProps) {
  return (
    <div className={styles.toolbar}>
      <div className={styles.toolActions}>
        {toolButtons.map((tool, index) => (
          <React.Fragment key={tool.tool}>
            {index === 3 || index === 6 ? <span className={styles.divider} /> : null}
            <IconButton
              icon={tool.icon}
              label={tool.label}
              accent={tool.accent}
              active={tool.tool === activeTool || (tool.tool === "palette" && paletteOpen)}
              onClick={() => onSelectTool(tool.tool)}
            />
          </React.Fragment>
        ))}

        <span className={styles.divider} />

        <IconButton icon="undo" label="Undo" onClick={onUndo} disabled={!canUndo} />
        <IconButton icon="redo" label="Redo" onClick={onRedo} disabled={!canRedo} />
        <IconButton icon="content_cut" label="Cut" onClick={onCut} disabled={!hasSelection} />
        <IconButton icon="content_copy" label="Copy" onClick={onCopy} disabled={!hasSelection} />
        <IconButton icon="content_paste" label="Paste" onClick={onPaste} disabled={!canPaste} />
      </div>

      <button type="button" className={styles.addPageButton} onClick={onAddPage} aria-label="Add Page">
        <span className="material-symbols-outlined" style={{ fontSize: 18 }} aria-hidden="true">
          add_circle
        </span>
        Add Page
      </button>
    </div>
  );
}
