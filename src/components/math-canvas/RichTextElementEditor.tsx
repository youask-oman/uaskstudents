"use client";

import React, { useCallback, useEffect, useMemo, useRef } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import type { Editor, JSONContent } from "@tiptap/core";
import { useStableEvent } from "@/hooks/useStableEvent";
import styles from "./MathCanvas.module.css";
import { buildRichTextExtensions } from "./rich-text/config";

export interface RichTextCommitPayload {
  text: string;
  richTextHtml?: string;
  richTextJson?: Record<string, unknown>;
}

interface RichTextElementEditorProps {
  elementId: string;
  initialText: string;
  initialHtml?: string;
  initialJson?: Record<string, unknown>;
  onCommit: (payload: RichTextCommitPayload) => void;
  onActivate: (editor: Editor | null, elementId: string | null) => void;
  onRequestClose: () => void;
}

const escapeHtml = (value: string): string =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

const fallbackHtml = (text: string): string => {
  const trimmed = text.trim();
  if (!trimmed) return "<p></p>";
  return `<p>${escapeHtml(trimmed).replace(/\n/g, "<br/>")}</p>`;
};

const asJsonContent = (value: Record<string, unknown> | undefined): JSONContent | null => {
  if (!value) return null;
  try {
    return JSON.parse(JSON.stringify(value)) as JSONContent;
  } catch {
    return null;
  }
};

const buildPayload = (editor: Editor): RichTextCommitPayload => {
  const plain = editor.getText({ blockSeparator: "\n" }).trim();
  const html = editor.getHTML();
  return {
    text: plain,
    richTextHtml: html,
    richTextJson: editor.getJSON() as Record<string, unknown>,
  };
};

const payloadSignature = (payload: RichTextCommitPayload): string =>
  `${payload.text}::${payload.richTextHtml || ""}`;

export default function RichTextElementEditor({
  elementId,
  initialText,
  initialHtml,
  initialJson,
  onCommit,
  onActivate,
  onRequestClose,
}: RichTextElementEditorProps) {
  const didHydrateRef = useRef(false);
  const dirtyRef = useRef(false);
  const editorRef = useRef<Editor | null>(null);
  const lastCommittedSignatureRef = useRef<string | null>(null);
  const onCommitEvent = useStableEvent(onCommit);
  const onActivateEvent = useStableEvent(onActivate);
  const onRequestCloseEvent = useStableEvent(onRequestClose);
  const initialContent = useMemo(
    () => asJsonContent(initialJson) || initialHtml || fallbackHtml(initialText),
    [initialHtml, initialJson, initialText],
  );

  const editor = useEditor({
    extensions: buildRichTextExtensions(),
    content: initialContent,
    autofocus: "end",
    immediatelyRender: false,
    editorProps: {
      attributes: {
        class: styles.richTextEditorContent,
      },
    },
    onFocus: ({ editor: focusedEditor }) => {
      onActivateEvent(focusedEditor, elementId);
    },
    onUpdate: ({ editor: updatedEditor }) => {
      if (!didHydrateRef.current) return;
      const signature = payloadSignature(buildPayload(updatedEditor));
      dirtyRef.current = signature !== lastCommittedSignatureRef.current;
    },
  }, [elementId, initialContent]);

  useEffect(() => {
    if (!editor) return;
    editorRef.current = editor;
    const signature = payloadSignature(buildPayload(editor));
    lastCommittedSignatureRef.current = signature;
    dirtyRef.current = false;
    didHydrateRef.current = true;
    return () => {
      editorRef.current = null;
      didHydrateRef.current = false;
      dirtyRef.current = false;
      lastCommittedSignatureRef.current = null;
    };
  }, [editor]);

  const commitIfChanged = useCallback(
    (reason: "blur" | "shortcut" | "unmount") => {
      const currentEditor = editorRef.current;
      if (!currentEditor || !didHydrateRef.current) return;
      const payload = buildPayload(currentEditor);
      const signature = payloadSignature(payload);
      if (signature === lastCommittedSignatureRef.current) {
        dirtyRef.current = false;
        if (reason === "unmount") return;
        return;
      }
      lastCommittedSignatureRef.current = signature;
      dirtyRef.current = false;
      onCommitEvent(payload);
    },
    [onCommitEvent],
  );

  useEffect(() => {
    if (!editor) return;
    const onBlur = () => {
      commitIfChanged("blur");
    };
    editor.on("blur", onBlur);
    return () => {
      editor.off("blur", onBlur);
    };
  }, [commitIfChanged, editor, onActivateEvent]);

  useEffect(() => {
    return () => {
      if (dirtyRef.current) {
        commitIfChanged("unmount");
      }
      onActivateEvent(null, null);
    };
  }, [commitIfChanged, onActivateEvent]);

  return (
    <div className={styles.canvasRichTextEditorWrap}>
      <EditorContent
        editor={editor}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            commitIfChanged("shortcut");
            onRequestCloseEvent();
          }
          if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
            event.preventDefault();
            commitIfChanged("shortcut");
            onRequestCloseEvent();
          }
        }}
      />
    </div>
  );
}
