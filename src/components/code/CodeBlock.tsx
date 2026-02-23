"use client";

import { useEffect, useMemo, useState } from "react";

export default function CodeBlock({ code, language = "python" }: { code: string; language?: string }) {
  const filename = useMemo(() => `solution.${language === "python" ? "py" : "txt"}`, [language]);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 1500);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard?.writeText(code);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  if (!code) return null;
  return (
    <div className="uask-code-block" style={{ border: "1px solid #e2e8f0", borderRadius: 10, overflow: "hidden" }}>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 10px", background: "#f8fafc", fontSize: 12 }}>
        <span>{filename}</span>
        <button
          type="button"
          onClick={handleCopy}
          style={{
            border: `1px solid ${copied ? "#16a34a" : "#cbd5e1"}`,
            background: copied ? "#dcfce7" : "#f8fafc",
            color: copied ? "#166534" : "#0f172a",
            borderRadius: 6,
            padding: "2px 8px",
            fontWeight: 600,
            transition: "all 120ms ease",
          }}
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre
        className="uask-code-block-pre"
        style={{
          margin: 0,
          padding: 12,
          background: "#0f172a",
          color: "#fef08a",
          overflowX: "auto",
          fontSize: 12,
          lineHeight: 1.5,
          whiteSpace: "pre",
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
        }}
      >
        <code className="uask-code-block-code" style={{ color: "#fef08a", background: "transparent" }}>{code}</code>
      </pre>
    </div>
  );
}
