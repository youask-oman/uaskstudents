"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import UnifiedMathRenderer from "@/components/math/UnifiedMathRenderer";

interface MarkdownMathContentProps {
  content: string;
  className?: string;
}

export default function MarkdownMathContent({ content, className }: MarkdownMathContentProps) {
  const normalized = (content || "")
    .replace(/\\\[((?:.|\n)*?)\\\]/g, (_, expr: string) => `\n$$${expr}$$\n`)
    .replace(/\\\((.+?)\\\)/g, (_m, expr: string) => `$${expr}$`);

  return (
    <div
      className={className}
      style={{
        whiteSpace: "normal",
        lineHeight: 1.65,
        wordBreak: "break-word",
        color: "inherit",
        fontSize: "inherit",
        fontFamily: "inherit",
      }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        components={{
          p: ({ children }) => <p style={{ margin: "0.5rem 0", color: "inherit", fontSize: "inherit" }}>{children}</p>,
          h1: ({ children }) => <h1 style={{ margin: "0.75rem 0 0.4rem", fontWeight: 700, fontSize: "1.1em", color: "inherit" }}>{children}</h1>,
          h2: ({ children }) => <h2 style={{ margin: "0.7rem 0 0.35rem", fontWeight: 700, fontSize: "1.02em", color: "inherit" }}>{children}</h2>,
          h3: ({ children }) => <h3 style={{ margin: "0.65rem 0 0.3rem", fontWeight: 700, fontSize: "0.98em", color: "inherit" }}>{children}</h3>,
          ul: ({ children }) => <ul style={{ margin: "0.4rem 0 0.6rem", paddingInlineStart: "1.1rem" }}>{children}</ul>,
          ol: ({ children }) => <ol style={{ margin: "0.4rem 0 0.6rem", paddingInlineStart: "1.1rem" }}>{children}</ol>,
          li: ({ children }) => <li style={{ margin: "0.2rem 0", color: "inherit", fontSize: "inherit" }}>{children}</li>,
          hr: () => <hr style={{ margin: "0.9rem 0", borderColor: "rgba(148,163,184,0.35)" }} />,
          code: ({ className: codeClassName, children }) => {
            const raw = String(children || "");
            const classNameText = String(codeClassName || "");
            const isMath =
              classNameText.includes("math-inline") ||
              classNameText.includes("math-display") ||
              classNameText.includes("language-math");
            if (isMath) {
              const mode = classNameText.includes("math-inline") ? "inline" : "block";
              return <UnifiedMathRenderer content={raw} mode={mode} />;
            }
            return <code style={{ whiteSpace: "pre-wrap" }}>{children}</code>;
          },
          pre: ({ children }) => <pre style={{ whiteSpace: "pre-wrap", overflowX: "auto" }}>{children}</pre>,
        }}
      >
        {normalized}
      </ReactMarkdown>
    </div>
  );
}
