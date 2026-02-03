"use client";

import React from "react";
import EditorToolbar from "./EditorToolbar";
import PaperPage from "./PaperPage";
import { CanvasPageData } from "./types";
import styles from "./MathCanvas.module.css";

interface CanvasWorkspaceProps {
  pages: CanvasPageData[];
  activePageId: string;
  onSelectPage: (pageId: string) => void;
  onAddPage: () => void;
  onOpenLatexEditor: () => void;
}

export default function CanvasWorkspace({
  pages,
  activePageId,
  onSelectPage,
  onAddPage,
  onOpenLatexEditor,
}: CanvasWorkspaceProps) {
  return (
    <section className={styles.centerColumn}>
      <EditorToolbar onAddPage={onAddPage} onOpenLatexEditor={onOpenLatexEditor} />
      <div className={styles.pagesStack}>
        {pages.map((page, index) => (
          <PaperPage
            key={page.id}
            page={page}
            index={index}
            active={page.id === activePageId}
            onActivate={() => onSelectPage(page.id)}
          />
        ))}
      </div>
    </section>
  );
}
