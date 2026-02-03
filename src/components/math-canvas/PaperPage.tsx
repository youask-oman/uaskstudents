"use client";

import React from "react";
import MathRenderer from "@/components/math/MathRendererSwitch";
import RecognitionBox from "./RecognitionBox";
import SolutionStepsBlock from "./SolutionStepsBlock";
import { CanvasPageData } from "./types";
import styles from "./MathCanvas.module.css";

interface PaperPageProps {
  page: CanvasPageData;
  index: number;
  active: boolean;
  onActivate: () => void;
}

export default function PaperPage({ page, index, active, onActivate }: PaperPageProps) {
  return (
    <article
      className={`${styles.paperPage} ${active ? styles.paperPageActive : ""}`}
      onClick={onActivate}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onActivate();
        }
      }}
    >
      <div className={styles.paperPageHeader}>
        <span className={styles.paperPageTitle}>Page {index + 1}</span>
      </div>
      <div className={styles.paperContent}>
        {page.blocks.length === 0 ? (
          <div style={{ color: "var(--text-muted)", fontSize: 14, minHeight: 220 }}>
            Blank page. Use the toolbar to add math blocks.
          </div>
        ) : (
          page.blocks.map((block) => {
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
          })
        )}
      </div>
    </article>
  );
}
