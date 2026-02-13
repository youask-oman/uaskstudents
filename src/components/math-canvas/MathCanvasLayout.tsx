"use client";

import React, { useEffect, useRef, useState } from "react";
import styles from "./MathCanvas.module.css";

interface MathCanvasLayoutProps {
  header: React.ReactNode;
  leftSidebar: React.ReactNode;
  workspace: React.ReactNode;
  rightSidebar: React.ReactNode;
}

export default function MathCanvasLayout({
  header,
  leftSidebar,
  workspace,
  rightSidebar,
}: MathCanvasLayoutProps) {
  const [leftOpen, setLeftOpen] = useState(false);
  const [rightOpen, setRightOpen] = useState(false);
  const CHAT_WIDTH_DEFAULT = 360;
  const CHAT_WIDTH_EXPANDED = 620;
  const [chatPanelWidth, setChatPanelWidth] = useState(CHAT_WIDTH_DEFAULT);
  const resizingRef = useRef(false);

  useEffect(() => {
    const onMove = (event: PointerEvent) => {
      if (!resizingRef.current || typeof window === "undefined") return;
      const viewportWidth = window.innerWidth;
      const next = Math.max(300, Math.min(760, viewportWidth - event.clientX));
      setChatPanelWidth(next);
    };

    const onUp = () => {
      resizingRef.current = false;
      if (typeof document !== "undefined") {
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      }
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, []);

  return (
    <div className={styles.root} style={{ ["--chat-panel-width" as string]: `${chatPanelWidth}px` }}>
      {header}
      <div className={styles.mobileCanvasActions}>
        <button
          type="button"
          className={styles.mobileCanvasButton}
          onClick={() => setLeftOpen(true)}
          aria-label="Open notebook sidebar"
        >
          <span className="material-symbols-outlined" aria-hidden="true">
            menu_book
          </span>
          Notebook
        </button>
        <button
          type="button"
          className={styles.mobileCanvasButton}
          onClick={() => setRightOpen(true)}
          aria-label="Open tutor sidebar"
        >
          <span className="material-symbols-outlined" aria-hidden="true">
            psychology
          </span>
          Tutor
        </button>
      </div>
      <div className={styles.body}>
        <div className={styles.desktopSidebar}>{leftSidebar}</div>
        {workspace}
        <div className={`${styles.desktopSidebar} ${styles.rightSidebarShell}`} style={{ width: chatPanelWidth }}>
          <button
            type="button"
            className={styles.chatResizeHandle}
            aria-label="Resize chat panel"
            onPointerDown={() => {
              resizingRef.current = true;
              if (typeof document !== "undefined") {
                document.body.style.cursor = "col-resize";
                document.body.style.userSelect = "none";
              }
            }}
          />
          <button
            type="button"
            className={styles.chatExpandButton}
            aria-label={chatPanelWidth >= CHAT_WIDTH_EXPANDED ? "Collapse chat panel" : "Expand chat panel"}
            title={chatPanelWidth >= CHAT_WIDTH_EXPANDED ? "Collapse" : "Expand"}
            onClick={() => {
              setChatPanelWidth((current) => (current >= CHAT_WIDTH_EXPANDED ? CHAT_WIDTH_DEFAULT : CHAT_WIDTH_EXPANDED));
            }}
          >
            <span className="material-symbols-outlined" aria-hidden="true">
              {chatPanelWidth >= CHAT_WIDTH_EXPANDED ? "compress" : "expand"}
            </span>
          </button>
          {rightSidebar}
        </div>
      </div>
      {leftOpen ? (
        <div className={styles.mobileOverlay} role="presentation" onClick={() => setLeftOpen(false)}>
          <div className={styles.mobileSheetLeft} role="dialog" aria-label="Notebook sidebar" onClick={(event) => event.stopPropagation()}>
            {leftSidebar}
          </div>
        </div>
      ) : null}
      {rightOpen ? (
        <div className={styles.mobileOverlay} role="presentation" onClick={() => setRightOpen(false)}>
          <div className={styles.mobileSheetRight} role="dialog" aria-label="Tutor sidebar" onClick={(event) => event.stopPropagation()}>
            {rightSidebar}
          </div>
        </div>
      ) : null}
    </div>
  );
}
