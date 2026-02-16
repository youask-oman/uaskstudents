"use client";

import React, { useCallback, useEffect, useState } from "react";
import type { Editor } from "@tiptap/core";
import { ToolType } from "./types";
import styles from "./MathCanvas.module.css";
import { getActiveListMode } from "./rich-text/config";

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

  // Rich text props
  activeEditor?: Editor | null;
  onNotice?: (message: string) => void;
  onInsertImage?: () => void;
}

const toolButtons: Array<{ tool: ToolType; icon: string; label: string; accent?: boolean }> = [
  { tool: "text", icon: "title", label: "Text (T)" },
  { tool: "math", icon: "functions", label: "Equation (LaTeX)", accent: true },
  { tool: "shape", icon: "crop_square", label: "Block / Highlight" },
  { tool: "compass", icon: "explore", label: "Compass (Circle/Arc)", accent: true },
  { tool: "ruler", icon: "straighten", label: "Ruler (Line/Measure)" },
  { tool: "graph", icon: "show_chart", label: "Plot Graph", accent: true },
  { tool: "eraser", icon: "ink_eraser", label: "Eraser" },
  { tool: "palette", icon: "palette", label: "Colors / Style", accent: true },
];

interface IconButtonProps {
  icon?: string;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  active?: boolean;
  accent?: boolean;
  extraClassName?: string;
  children?: React.ReactNode;
}

function IconButton({
  icon,
  label,
  onClick,
  disabled,
  active,
  accent,
  extraClassName,
  children,
}: IconButtonProps) {
  return (
    <button
      type="button"
      className={`${styles.toolButton} ${active ? styles.toolButtonActive : ""} ${extraClassName || ""}`.trim()}
      title={label}
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      onMouseDown={(e) => {
        // Prevent focus loss from editor when clicking formatting buttons
        if (!disabled) e.preventDefault();
      }}
    >
      {icon ? (
        <span
          className={`material-symbols-outlined ${accent ? styles.toolAccent : ""}`}
          style={{ fontSize: 20 }}
          aria-hidden="true"
        >
          {icon}
        </span>
      ) : children}
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
  activeEditor,
  onNotice,
  onInsertImage,
}: EditorToolbarProps) {
  const getFocusedTextInput = (): HTMLTextAreaElement | HTMLInputElement | null => {
    if (typeof document === "undefined") return null;
    const active = document.activeElement;
    if (active instanceof HTMLTextAreaElement) return active;
    if (active instanceof HTMLInputElement && active.type === "text") return active;
    return null;
  };

  const applyToFocusedInput = (label: string, value?: string): boolean => {
    const input = getFocusedTextInput();
    if (!input) return false;

    const start = input.selectionStart ?? 0;
    const end = input.selectionEnd ?? 0;
    const selected = input.value.slice(start, end);
    const fallbackSelected = selected || "text";

    if (label === "bold" || label === "italic") {
      // Plain input/textarea fields cannot render rich text formatting.
      return false;
    } else if (label === "bulleted list") {
      const block = selected || input.value.slice(start);
      const lines = block.split("\n").map((line) => (line.trim() ? `- ${line}` : line)).join("\n");
      input.setRangeText(lines, start, end, "end");
    } else if (label === "numbered list") {
      const block = selected || input.value.slice(start);
      const lines = block.split("\n").map((line, idx) => (line.trim() ? `${idx + 1}. ${line}` : line)).join("\n");
      input.setRangeText(lines, start, end, "end");
    } else if (label === "link") {
      const href = value || "https://";
      const text = fallbackSelected;
      input.setRangeText(`[${text}](${href})`, start, end, "end");
    } else if (label === "unlink") {
      const raw = selected || input.value.slice(start, end);
      const next = raw.replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1");
      input.setRangeText(next, start, end, "end");
    } else {
      return false;
    }

    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.focus();
    return true;
  };

  const buildViewState = useCallback(
    (editor: Editor | null) => ({
      listMode: getActiveListMode(editor),
      bold: Boolean(editor?.isActive("bold")),
      italic: Boolean(editor?.isActive("italic")),
    }),
    [],
  );

  const [, setEditorVersion] = useState(0);
  const viewState = buildViewState(activeEditor || null);

  useEffect(() => {
    if (!activeEditor) return;

    const handler = () => {
      setEditorVersion((prev) => prev + 1);
    };

    activeEditor.on("selectionUpdate", handler);
    activeEditor.on("transaction", handler);

    return () => {
      activeEditor.off("selectionUpdate", handler);
      activeEditor.off("transaction", handler);
    };
  }, [activeEditor, buildViewState]);

  const richTextEnabled = Boolean(activeEditor && activeEditor.isEditable);

  const runExecFallback = (command: string, value?: string) => {
    try {
      document.execCommand(command, false, value);
      return true;
    } catch {
      return false;
    }
  };

  const runRichCommand = (label: string, command: (editor: Editor) => boolean) => {
    if (!activeEditor || !activeEditor.isEditable) {
      if (label === "bold" || label === "italic") {
        onNotice?.(`"${label[0].toUpperCase()}${label.slice(1)}" works only in rich text fields.`);
        return;
      }
      if (applyToFocusedInput(label)) return;
      const map: Record<string, string> = {
        bold: "bold",
        italic: "italic",
        "bulleted list": "insertUnorderedList",
        "numbered list": "insertOrderedList",
      };
      const fallback = map[label];
      if (fallback && runExecFallback(fallback)) return;
      onNotice?.(`Format "${label}" is unavailable in this field.`);
      return;
    }
    try {
      const success = command(activeEditor);
      if (!success) {
        onNotice?.(`Format "${label}" not available here.`);
      }
    } catch (err) {
      console.error(`Rich command error [${label}]`, err);
      onNotice?.("Failed to apply formatting.");
    }
  };

  return (
    <div className={styles.toolbar} style={{ position: "sticky", top: 0, zIndex: 2040 }}>
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

        {/* Rich Text Controls moved here */}
        <IconButton
          icon="format_list_bulleted"
          label="Bulleted list"
          active={viewState.listMode === "bulleted"}
          onClick={() => runRichCommand("bulleted list", (editor) => editor.chain().focus().toggleBulletList().run())}
        />
        <IconButton
          icon="format_list_numbered"
          label="Numbered list"
          active={viewState.listMode === "numbered"}
          onClick={() => runRichCommand("numbered list", (editor) => editor.chain().focus().toggleOrderedList().run())}
        />
        <IconButton
          label="Bold"
          active={viewState.bold}
          onClick={() => runRichCommand("bold", (editor) => editor.chain().focus().toggleBold().run())}
        >
          <span style={{ fontWeight: 700, fontSize: 16 }}>B</span>
        </IconButton>
        <IconButton
          label="Italic"
          active={viewState.italic}
          onClick={() => runRichCommand("italic", (editor) => editor.chain().focus().toggleItalic().run())}
        >
          <span style={{ fontStyle: "italic", fontSize: 16, fontFamily: "serif" }}>I</span>
        </IconButton>
        <IconButton
          icon="link"
          label="Link"
          onClick={() => {
            const current = activeEditor?.getAttributes("link").href || "";
            const url = prompt("Link URL:", current);
            if (url !== null) {
              if (url) {
                if (activeEditor && activeEditor.isEditable) {
                  runRichCommand("link", (editor) =>
                    editor.chain().focus().extendMarkRange("link").setLink({ href: url }).run(),
                  );
                } else {
                  if (!applyToFocusedInput("link", url) && !runExecFallback("createLink", url)) {
                    onNotice?.("Link is unavailable in this field.");
                  }
                }
              } else {
                if (activeEditor && activeEditor.isEditable) {
                  runRichCommand("unlink", (editor) => editor.chain().focus().unsetLink().run());
                } else {
                  if (!applyToFocusedInput("unlink")) runExecFallback("unlink");
                }
              }
            }
          }}
        />
        <IconButton
          icon="grid_on"
          label="Insert Table"
          onClick={() => runRichCommand("table", (editor) => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run())}
        />
        <IconButton
          icon="add_photo_alternate"
          label="Insert Image"
          disabled={!richTextEnabled && !onInsertImage}
          onClick={onInsertImage || (() => { })}
        />

        <span className={styles.divider} />

        <IconButton
          icon="undo"
          label="Undo"
          onClick={richTextEnabled ? () => activeEditor?.chain().focus().undo().run() : onUndo}
          disabled={richTextEnabled ? !activeEditor?.can().undo() : !canUndo}
        />
        <IconButton
          icon="redo"
          label="Redo"
          onClick={richTextEnabled ? () => activeEditor?.chain().focus().redo().run() : onRedo}
          disabled={richTextEnabled ? !activeEditor?.can().redo() : !canRedo}
        />
        <IconButton
          icon="content_cut"
          label="Cut"
          onClick={richTextEnabled ? () => {
            document.execCommand("cut");
          } : onCut}
          disabled={richTextEnabled ? false : !hasSelection}
        />
        <IconButton
          icon="content_copy"
          label="Copy"
          onClick={richTextEnabled ? () => {
            document.execCommand("copy");
          } : onCopy}
          disabled={richTextEnabled ? false : !hasSelection}
        />
        <IconButton
          icon="content_paste"
          label="Paste"
          onClick={richTextEnabled ? () => {
            navigator.clipboard.readText().then(text => {
              activeEditor?.chain().focus().insertContent(text).run();
            });
          } : onPaste}
          disabled={richTextEnabled ? false : !canPaste}
        />
      </div>
    </div>
  );
}
