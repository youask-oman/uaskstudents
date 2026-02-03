"use client";

import React from "react";
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
  return (
    <div className={styles.root}>
      {header}
      <div className={styles.body}>
        {leftSidebar}
        {workspace}
        {rightSidebar}
      </div>
    </div>
  );
}
