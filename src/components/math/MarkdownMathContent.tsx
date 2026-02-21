"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import UnifiedMathRenderer from "@/components/math/UnifiedMathRenderer";
import { normalizeProseMath } from "@/components/math/mathNormalize";

interface MarkdownMathContentProps {
  content: string;
  className?: string;
}

const childrenToText = (children: React.ReactNode): string => {
  if (typeof children === "string") return children;
  if (typeof children === "number") return String(children);
  if (Array.isArray(children)) return children.map(childrenToText).join("");
  return "";
};

const getMathRaw = (props: {
  children?: React.ReactNode;
  value?: unknown;
  node?: unknown;
}): string => {
  const valueText = typeof props.value === "string" ? props.value : "";
  const nodeValue =
    props.node && typeof props.node === "object" && "value" in (props.node as Record<string, unknown>)
      ? ((props.node as Record<string, unknown>).value as unknown)
      : undefined;
  const nodeValueText = typeof nodeValue === "string" ? nodeValue : "";
  const childrenText = childrenToText(props.children);
  return valueText || nodeValueText || childrenText || "";
};

export default function MarkdownMathContent({ content, className }: MarkdownMathContentProps) {
  const normalized = normalizeProseMath(content || "")
    .replace(/\\\[((?:.|\n)*?)\\\]/g, (_, expr: string) => `\n$$${expr}$$\n`)
    .replace(/\\\((.+?)\\\)/g, (_m, expr: string) => `$${expr}$`);

  const markdownComponents: Record<string, React.ComponentType<any>> = {
    inlineMath: (props: { children?: React.ReactNode; value?: unknown; node?: unknown }) => {
      const raw = getMathRaw(props);
      return <UnifiedMathRenderer content={raw} mode="inline" />;
    },
    math: (props: { children?: React.ReactNode; value?: unknown; node?: unknown }) => {
      const raw = getMathRaw(props);
      return <UnifiedMathRenderer content={raw} mode="block" />;
    },
    p: ({ children }: { children?: React.ReactNode }) => <p style={{ margin: "0.5rem 0", color: "inherit", fontSize: "inherit" }}>{children}</p>,
    h1: ({ children }: { children?: React.ReactNode }) => <h1 style={{ margin: "0.75rem 0 0.4rem", fontWeight: 700, fontSize: "1.1em", color: "inherit" }}>{children}</h1>,
    h2: ({ children }: { children?: React.ReactNode }) => <h2 style={{ margin: "0.7rem 0 0.35rem", fontWeight: 700, fontSize: "1.02em", color: "inherit" }}>{children}</h2>,
    h3: ({ children }: { children?: React.ReactNode }) => <h3 style={{ margin: "0.65rem 0 0.3rem", fontWeight: 700, fontSize: "0.98em", color: "inherit" }}>{children}</h3>,
    ul: ({ children }: { children?: React.ReactNode }) => <ul style={{ margin: "0.4rem 0 0.6rem", paddingInlineStart: "1.1rem" }}>{children}</ul>,
    ol: ({ children }: { children?: React.ReactNode }) => <ol style={{ margin: "0.4rem 0 0.6rem", paddingInlineStart: "1.1rem" }}>{children}</ol>,
    li: ({ children }: { children?: React.ReactNode }) => <li style={{ margin: "0.2rem 0", color: "inherit", fontSize: "inherit" }}>{children}</li>,
    hr: () => <hr style={{ margin: "0.9rem 0", borderColor: "rgba(148,163,184,0.35)" }} />,
    code: ({ className: codeClassName, children }: { className?: string; children?: React.ReactNode }) => {
      const raw = childrenToText(children);
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
    pre: ({ children }: { children?: React.ReactNode }) => <pre style={{ whiteSpace: "pre-wrap", overflowX: "auto" }}>{children}</pre>,
  };

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
        components={markdownComponents as any}
      >
        {normalized}
      </ReactMarkdown>
    </div>
  );
}
