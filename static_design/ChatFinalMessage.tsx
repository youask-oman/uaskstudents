"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

export function ChatFinalMessage({ content }: { content: string }) {
  // ChatGPT-style: render Markdown + LaTeX, preserve paragraphs and lists.
  return (
    <div className="prose max-w-none whitespace-pre-wrap">
      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
