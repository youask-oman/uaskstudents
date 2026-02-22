"use client";

import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import remarkLatexDelimiters from "@/lib/remark/remarkLatexDelimiters";
import MathSvg from "@/components/math/MathSvg";

type MarkdownMathContentProps = {
  content: string;
  className?: string;
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

export default function MarkdownMathContent({ content, className }: MarkdownMathContentProps) {
  const processedContent = useMemo(() => {
    if (!content) return "";

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
  }, [content]);

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
        components={{
          math: (props: any) => {
            const tex = String(props.tex || props.value || childrenToRawText(props.children) || "");
            if (!tex) return null;
            return <MathSvg tex={tex} display={true} />;
          },
          inlineMath: (props: any) => {
            const tex = String(props.tex || props.value || childrenToRawText(props.children) || "");
            if (!tex) return null;
            return <MathSvg tex={tex} display={false} />;
          },
          "latex-math-block": (props: any) => <MathSvg tex={String(props.tex || "")} display={true} />,
          "latex-math-inline": (props: any) => <MathSvg tex={String(props.tex || "")} display={false} />,
          code: ({ className: codeClassName, children }: any) => {
            const classText = String(codeClassName || "");
            const raw = childrenToRawText(children);
            const explicitMath = isExplicitMathClass(classText);
            if (explicitMath) {
              const display = classText.includes("math-display") || !classText.includes("math-inline");
              return <MathSvg tex={raw} display={display} />;
            }
            return (
              <code
                className={codeClassName}
                style={{ whiteSpace: "pre-wrap", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" }}
              >
                {children}
              </code>
            );
          },
          pre: ({ children }: any) => <pre style={{ whiteSpace: "pre-wrap", overflowX: "auto" }}>{children}</pre>,
        } as any}
      >
        {processedContent}
      </ReactMarkdown>
    </span>
  );
}
