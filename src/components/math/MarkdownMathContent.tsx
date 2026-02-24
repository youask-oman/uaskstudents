"use client";

import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import remarkLatexDelimiters from "@/lib/remark/remarkLatexDelimiters";
import MathSvg from "@/components/math/MathSvg";

interface MarkdownMathContentProps {
  content: string;
  className?: string;
  /** If true, skips custom layout transformations like forced new lines for bold text/labels. */
  simple?: boolean;
}

type LatexLikeProps = {
  tex?: unknown;
  value?: unknown;
  children?: React.ReactNode;
};

type CodeLikeProps = {
  className?: string;
  children?: React.ReactNode;
};

function childrenToRawText(children: React.ReactNode): string {
  if (typeof children === "string") return children;
  if (typeof children === "number") return String(children);
  if (Array.isArray(children)) return children.map(childrenToRawText).join("");
  return "";
}

function isExplicitMathClass(className: string): boolean {
  return (
    className.includes("math-inline") ||
    className.includes("math-display") ||
    className.includes("language-math") ||
    /language-(tex|latex|math)\b/.test(className) ||
    className.includes("tex")
  );
}

export default function MarkdownMathContent({ content, className, simple }: MarkdownMathContentProps) {
  const processedContent = useMemo(() => {
    if (!content) return "";

    if (simple) return content;

    let processed = content;

    // 1. Ensure "Answer:" is bold and on a new line.
    processed = processed.replace(/(?:\s|^)(Answer[:.]?)/gi, "\n\n**$1**\n");

    // 2. Ensure bold text (**...**) starts on a new line if it's not already.
    // We look for bold blocks that are preceded by characters other than newlines.
    processed = processed.replace(/([^\n])(\s*)(\*\*.*?\*\*)/g, "$1\n\n$3");

    // 3. Split sentences into new paragraphs, but be careful not to break math or bold blocks.
    // Logic: Look for a dot followed by space(s) and a capital letter.
    // We avoid splitting if the dot is preceded by a digit (decimal) or if it's a common abbreviation.
    processed = processed.replace(/(?<!\d|[A-Z])\. +(?=[A-Z])/g, ".\n\n");

    // Clean up excessive newlines
    processed = processed.replace(/\n{3,}/g, "\n\n").trim();

    return processed;
  }, [content, simple]);

  const components: Components = {
    math: (props) => {
      const p = props as LatexLikeProps;
      const tex = String(p.tex || p.value || childrenToRawText(p.children) || "");
      if (!tex) return null;
      return <MathSvg tex={tex} display={true} />;
    },
    inlineMath: (props) => {
      const p = props as LatexLikeProps;
      const tex = String(p.tex || p.value || childrenToRawText(p.children) || "");
      if (!tex) return null;
      return <MathSvg tex={tex} display={false} />;
    },
    "latex-math-block": (props) => {
      const p = props as LatexLikeProps;
      return <MathSvg tex={String(p.tex || "")} display={true} />;
    },
    "latex-math-inline": (props) => {
      const p = props as LatexLikeProps;
      return <MathSvg tex={String(p.tex || "")} display={false} />;
    },
    code: (props) => {
      const p = props as CodeLikeProps;
      const classText = String(p.className || "");
      const raw = childrenToRawText(p.children);
      const explicitMath = isExplicitMathClass(classText);
      if (explicitMath) {
        const display = classText.includes("math-display") || !classText.includes("math-inline");
        return <MathSvg tex={raw} display={display} />;
      }
      return (
        <code
          className={p.className}
          style={{ whiteSpace: "pre-wrap", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" }}
        >
          {p.children}
        </code>
      );
    },
    pre: (props) => {
      const p = props as CodeLikeProps;
      return <pre style={{ whiteSpace: "pre-wrap", overflowX: "auto" }}>{p.children}</pre>;
    },
  };

  return (
    <span
      className={className}
      style={{
        display: "block",
        lineHeight: 1.8,
        wordBreak: "break-word",
        color: "inherit",
        fontSize: "inherit",
        fontFamily: "inherit",
      }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkLatexDelimiters, remarkMath]}
        components={components}
      >
        {processedContent}
      </ReactMarkdown>
    </span>
  );
}
