"use client";

import React from "react";
import styles from "./MathCanvas.module.css";
import { SavedPaperVersion } from "./types";

interface RichTextToolbarProps {
  canExport: boolean;
  exportingDocx: boolean;
  exportingPdf: boolean;
  savingVersion: boolean;
  onExportPdf: () => void;
  onExportDocx: () => void;
  onSaveVersion: () => void;
  onAddPage: () => void;
  onDeletePage: () => void;
  canDeletePage: boolean;
  canShare: boolean;
  onShare: () => void;

  // Version Loading props
  versionOptions: SavedPaperVersion[];
  selectedVersionKey: string;
  setSelectedVersionKey: (key: string) => void;
  handleLoadVersion: () => void;
  selectedVersion: SavedPaperVersion | null;
}

export default function RichTextToolbar({
  canExport,
  exportingDocx,
  exportingPdf,
  savingVersion,
  onExportPdf,
  onExportDocx,
  onSaveVersion,
  onAddPage,
  onDeletePage,
  canDeletePage,
  canShare,
  onShare,
  versionOptions,
  selectedVersionKey,
  setSelectedVersionKey,
  handleLoadVersion,
  selectedVersion,
}: RichTextToolbarProps) {
  return (
    <div className={styles.richTextToolbar} data-no-export="true">
      {/* Group 1: Page & Export Actions (Align Left) */}
      <button
        type="button"
        className={`${styles.actionButtonDual} ${styles.actionButtonSecondary}`}
        onClick={() => {
          if (window.confirm("Delete current page? This cannot be undone.")) {
            onDeletePage();
          }
        }}
        aria-label="Delete Page"
        disabled={!canDeletePage}
        style={{ height: 36, padding: "0 8px", minWidth: 90 }}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 20 }} aria-hidden="true">
          delete
        </span>
        <div className={styles.actionButtonTextCol}>
          <span className={styles.actionTop} style={{ fontSize: 9 }}>Delete</span>
          <span className={styles.actionBottom} style={{ fontSize: 12 }}>Page</span>
        </div>
      </button>

      <button
        type="button"
        className={`${styles.actionButtonDual} ${styles.actionButtonPrimary}`}
        onClick={onAddPage}
        aria-label="New Page"
        style={{ height: 36, padding: "0 8px", minWidth: 90 }}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 20 }} aria-hidden="true">
          add_circle
        </span>
        <div className={styles.actionButtonTextCol}>
          <span className={styles.actionTop} style={{ fontSize: 9 }}>New</span>
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
            disabled={exportingPdf}
            style={{ height: 36, padding: "0 8px", minWidth: 90 }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 20 }} aria-hidden="true">
              picture_as_pdf
            </span>
            <div className={styles.actionButtonTextCol}>
              <span className={styles.actionTop} style={{ fontSize: 9 }}>EXPORT</span>
              <span className={styles.actionBottom} style={{ fontSize: 12 }}>{exportingPdf ? "..." : "PDF"}</span>
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
      <button
        type="button"
        className={`${styles.actionButtonDual} ${styles.actionButtonSecondary}`}
        onClick={onShare}
        aria-label="Share Solution"
        disabled={!canShare}
        style={{ height: 36, padding: "0 8px", minWidth: 90 }}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 20 }} aria-hidden="true">
          share
        </span>
        <div className={styles.actionButtonTextCol}>
          <span className={styles.actionTop} style={{ fontSize: 9 }}>SHARE</span>
          <span className={styles.actionBottom} style={{ fontSize: 12 }}>Link</span>
        </div>
      </button>

      {/* Spacer pushes the next elements to the right */}
      <div className={styles.spacer} />

      {/* Group 2: Version Loading (Align Right) */}
      {versionOptions.length > 0 && (
        <div className={styles.versionLoadPanelContainer} style={{ display: 'flex', alignItems: 'center' }}>
          <div className={styles.divider} style={{ height: 24, margin: "0 12px" }} />
          <div className={styles.versionLoadPanel} style={{ border: "none", padding: 0, background: "transparent", margin: 0 }}>
            <span className={styles.versionLoadLabel} style={{ fontSize: 13, fontWeight: 700, color: "#475569" }}>Saved versions</span>
            <select
              className={styles.versionLoadSelect}
              value={selectedVersionKey}
              onChange={(event) => setSelectedVersionKey(event.target.value)}
              style={{ height: 32, fontSize: 13 }}
            >
              {versionOptions.map((version) => {
                const savedAtLabel = version.savedAt ? new Date(version.savedAt).toLocaleString() : "";
                return (
                  <option key={version.key} value={version.key}>
                    {`v${version.version} - ${version.title}${savedAtLabel ? ` (${savedAtLabel})` : ""}`}
                  </option>
                );
              })}
            </select>
            <button
              type="button"
              className={styles.versionLoadButton}
              disabled={!selectedVersion}
              onClick={handleLoadVersion}
              style={{ height: 32, padding: "0 12px", fontSize: 13 }}
            >
              Load
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
