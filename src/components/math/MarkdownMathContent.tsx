"use client";

import React from "react";
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
  return (
    <div
      className={className}
      style={{
        lineHeight: 1.65,
        wordBreak: "break-word",
        color: "inherit",
        fontSize: "inherit",
        fontFamily: "inherit",
      }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkLatexDelimiters, remarkMath]}
        components={{
          inlineMath: ({ value }: any) => <MathSvg tex={String(value || "")} display={false} />,
          math: ({ value }: any) => <MathSvg tex={String(value || "")} display={true} />,
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
        {content || ""}
      </ReactMarkdown>
    </div>
  );
}
