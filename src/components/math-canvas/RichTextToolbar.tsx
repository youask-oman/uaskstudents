"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import type { Editor } from "@tiptap/core";
import styles from "./MathCanvas.module.css";
import {
  applyStyleToEditor,
  getActiveListMode,
  getActiveStyle,
  RICH_TEXT_STYLE_OPTIONS,
  type RichTextListOption,
} from "./rich-text/config";
import { validateAndNormalizeLink } from "./rich-text/linkUtils";

interface RichTextToolbarProps {
  activeEditor: Editor | null;
  onNotice?: (message: string) => void;
  canExport: boolean;
  exportingDocx: boolean;
  savingVersion: boolean;
  onExportPdf: () => void;
  onExportDocx: () => void;
  onSaveVersion: () => void;
  onAddPage: () => void;
  onInsertImage: () => void;
}


const notify = (handler: ((message: string) => void) | undefined, message: string) => {
  if (handler) handler(message);
};

export default function RichTextToolbar({
  activeEditor,
  onNotice,
  canExport,
  exportingDocx,
  savingVersion,
  onExportPdf,
  onExportDocx,
  onSaveVersion,
  onAddPage,
  onInsertImage,
}: RichTextToolbarProps) {
  const buildViewState = useCallback(
    (editor: Editor | null) => ({
      style: getActiveStyle(editor),
      listMode: getActiveListMode(editor),
      bold: Boolean(editor?.isActive("bold")),
      italic: Boolean(editor?.isActive("italic")),
    }),
    [],
  );

  const [viewState, setViewState] = useState(() => buildViewState(activeEditor));
  const [showLinkMenu, setShowLinkMenu] = useState(false);
  const [showTableMenu, setShowTableMenu] = useState(false);
  const [linkDraft, setLinkDraft] = useState("");

  useEffect(() => {
    setViewState(buildViewState(activeEditor));
  }, [activeEditor, buildViewState]);

  useEffect(() => {
    if (!activeEditor) return;
    const update = () => {
      setViewState((previous) => {
        const next = buildViewState(activeEditor);
        if (
          previous.style === next.style &&
          previous.listMode === next.listMode &&
          previous.bold === next.bold &&
          previous.italic === next.italic
        ) {
          return previous;
        }
        return next;
      });
    };
    activeEditor.on("selectionUpdate", update);
    activeEditor.on("transaction", update);
    activeEditor.on("focus", update);
    activeEditor.on("blur", update);
    return () => {
      activeEditor.off("selectionUpdate", update);
      activeEditor.off("transaction", update);
      activeEditor.off("focus", update);
      activeEditor.off("blur", update);
    };
  }, [activeEditor, buildViewState]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!activeEditor || !activeEditor.isEditable) return;
      if (!(event.ctrlKey || event.metaKey)) return;
      if (event.key.toLowerCase() !== "k") return;
      event.preventDefault();
      setShowLinkMenu(true);
      setShowTableMenu(false);
      const href = String(activeEditor.getAttributes("link").href || "");
      setLinkDraft(href);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activeEditor]);

  const enabled = Boolean(activeEditor && activeEditor.isEditable);
  const currentStyle = useMemo(() => viewState.style, [viewState.style]);
  const currentListMode = useMemo(() => viewState.listMode, [viewState.listMode]);
  const isBold = viewState.bold;
  const isItalic = viewState.italic;

  const runCommand = useCallback(
    (label: string, command: (editor: Editor) => boolean) => {
      if (!activeEditor || !activeEditor.isEditable) {
        notify(onNotice, "Select a text block to format.");
        return;
      }
      try {
        const ok = command(activeEditor);
        if (!ok) notify(onNotice, `Could not apply ${label}.`);
      } catch (error) {
        console.error(`rich-text command failed: ${label}`, error);
        notify(onNotice, `Could not apply ${label}.`);
      }
    },
    [activeEditor, onNotice],
  );

  const applyLink = useCallback(() => {
    const parsed = validateAndNormalizeLink(linkDraft);
    if (!parsed.ok || !parsed.normalized) {
      notify(onNotice, parsed.error || "Could not apply formatting");
      return;
    }
    const href = parsed.normalized;
    runCommand("link", (editor) => {
      if (!editor.can().chain().focus().extendMarkRange("link").setLink({ href }).run()) return false;
      return editor
        .chain()
        .focus()
        .extendMarkRange("link")
        .setLink({ href, target: "_blank", rel: "noopener noreferrer nofollow" })
        .run();
    });
    setShowLinkMenu(false);
  }, [linkDraft, onNotice, runCommand]);

  return (
    <div className={styles.richTextToolbar} data-no-export="true">
      <select
        aria-label="Text style"
        className={styles.richToolbarSelect}
        disabled={!enabled}
        value={currentStyle}
        onChange={(event) => runCommand("style", (editor) => applyStyleToEditor(editor, event.target.value as typeof currentStyle))}
      >
        {RICH_TEXT_STYLE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      <button
        type="button"
        aria-label="Bulleted list"
        className={`${styles.richToolbarButton} ${currentListMode === "bulleted" ? styles.richToolbarButtonActive : ""}`.trim()}
        disabled={!enabled}
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => runCommand("bulleted list", (editor) => editor.chain().focus().toggleBulletList().run())}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 18 }} aria-hidden="true">
          format_list_bulleted
        </span>
      </button>

      <button
        type="button"
        aria-label="Numbered list"
        className={`${styles.richToolbarButton} ${currentListMode === "numbered" ? styles.richToolbarButtonActive : ""}`.trim()}
        disabled={!enabled}
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => runCommand("numbered list", (editor) => editor.chain().focus().toggleOrderedList().run())}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 18 }} aria-hidden="true">
          format_list_numbered
        </span>
      </button>

      <button
        type="button"
        aria-label="Bold"
        className={`${styles.richToolbarButton} ${isBold ? styles.richToolbarButtonActive : ""}`.trim()}
        disabled={!enabled}
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => runCommand("bold", (editor) => editor.chain().focus().toggleBold().run())}
      >
        B
      </button>
      <button
        type="button"
        aria-label="Italic"
        className={`${styles.richToolbarButton} ${isItalic ? styles.richToolbarButtonActive : ""}`.trim()}
        disabled={!enabled}
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => runCommand("italic", (editor) => editor.chain().focus().toggleItalic().run())}
      >
        I
      </button>

      <div className={styles.richToolbarMenuWrap}>
        <button
          type="button"
          aria-label="Link"
          className={styles.richToolbarButton}
          disabled={!enabled}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            setShowTableMenu(false);
            setShowLinkMenu((prev) => !prev);
            const href = String(activeEditor?.getAttributes("link").href || "");
            setLinkDraft(href);
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 18 }} aria-hidden="true">
            link
          </span>
        </button>
        {showLinkMenu && enabled ? (
          <div className={styles.richToolbarPopup} role="dialog" aria-label="Edit link">
            <input
              type="text"
              className={styles.richToolbarInput}
              placeholder="https://example.com"
              value={linkDraft}
              onChange={(event) => setLinkDraft(event.target.value)}
            />
            <div className={styles.richToolbarPopupActions}>
              <button type="button" className={styles.blockActionButton} onClick={applyLink}>
                Apply
              </button>
              <button
                type="button"
                className={styles.blockActionButton}
                onClick={() => {
                  runCommand("remove link", (editor) => editor.chain().focus().unsetLink().run());
                  setShowLinkMenu(false);
                }}
              >
                Remove
              </button>
            </div>
          </div>
        ) : null}
      </div>

      <div className={styles.richToolbarMenuWrap}>
        <button
          type="button"
          aria-label="Table"
          className={styles.richToolbarButton}
          disabled={!enabled}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            setShowLinkMenu(false);
            setShowTableMenu((prev) => !prev);
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 18 }} aria-hidden="true">
            table_chart
          </span>
        </button>
        {showTableMenu && enabled ? (
          <div className={styles.richToolbarPopup} role="menu" aria-label="Table options">
            <button
              type="button"
              className={styles.blockActionButton}
              onClick={() => runCommand("insert table", (editor) => editor.chain().focus().insertTable({ rows: 3, cols: 3 }).run())}
            >
              Insert 3x3 table
            </button>
            <button
              type="button"
              className={styles.blockActionButton}
              onClick={() => runCommand("add row", (editor) => editor.chain().focus().addRowAfter().run())}
            >
              Add row
            </button>
            <button
              type="button"
              className={styles.blockActionButton}
              onClick={() => runCommand("add column", (editor) => editor.chain().focus().addColumnAfter().run())}
            >
              Add column
            </button>
            <button
              type="button"
              className={styles.blockActionButton}
              onClick={() => runCommand("delete table", (editor) => editor.chain().focus().deleteTable().run())}
            >
              Delete table
            </button>
          </div>
        ) : null}
      </div>

      <div className={styles.divider} style={{ height: 20 }} />

      <button
        type="button"
        aria-label="Insert Image"
        className={styles.richToolbarButton}
        onClick={onInsertImage}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 20 }} aria-hidden="true">
          add_photo_alternate
        </span>
      </button>

      <div className={styles.divider} style={{ height: 20 }} />

      <button
        type="button"
        className={`${styles.actionButtonDual} ${styles.actionButtonPrimary}`}
        onClick={onAddPage}
        aria-label="Add Page"
        style={{ height: 36, padding: "0 8px", minWidth: 90 }}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 20 }} aria-hidden="true">
          add_circle
        </span>
        <div className={styles.actionButtonTextCol}>
          <span className={styles.actionTop} style={{ fontSize: 9 }}>Add</span>
          <span className={styles.actionBottom} style={{ fontSize: 12 }}>Page</span>
        </div>
      </button>

      {canExport ? (
        <>
          <button
            type="button"
            className={`${styles.actionButtonDual} ${styles.actionButtonSecondary}`}
            onClick={onExportPdf}
            aria-label="Export PDF"
            style={{ height: 36, padding: "0 8px", minWidth: 90 }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 20 }} aria-hidden="true">
              picture_as_pdf
            </span>
            <div className={styles.actionButtonTextCol}>
              <span className={styles.actionTop} style={{ fontSize: 9 }}>EXPORT</span>
              <span className={styles.actionBottom} style={{ fontSize: 12 }}>PDF</span>
            </div>
          </button>
          <button
            type="button"
            className={`${styles.actionButtonDual} ${styles.actionButtonSecondary}`}
            onClick={onExportDocx}
            aria-label="Export DOCX"
            disabled={exportingDocx}
            style={{ height: 36, padding: "0 8px", minWidth: 90 }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 20 }} aria-hidden="true">
              description
            </span>
            <div className={styles.actionButtonTextCol}>
              <span className={styles.actionTop} style={{ fontSize: 9 }}>EXPORT</span>
              <span className={styles.actionBottom} style={{ fontSize: 12 }}>{exportingDocx ? "..." : "DOCX"}</span>
            </div>
          </button>
        </>
      ) : null}

      <button
        type="button"
        className={`${styles.actionButtonDual} ${styles.actionButtonSecondary}`}
        onClick={onSaveVersion}
        aria-label="Save Version"
        disabled={savingVersion}
        style={{ height: 36, padding: "0 8px", minWidth: 90 }}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 20 }} aria-hidden="true">
          save
        </span>
        <div className={styles.actionButtonTextCol}>
          <span className={styles.actionTop} style={{ fontSize: 9 }}>SAVE</span>
          <span className={styles.actionBottom} style={{ fontSize: 12 }}>{savingVersion ? "..." : "Version"}</span>
        </div>
      </button>

    </div>
  );
}
