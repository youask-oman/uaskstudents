"use client";

import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

type LegalMarkdownClientProps = {
  content: string;
};

export default function LegalMarkdownClient({ content }: LegalMarkdownClientProps) {
  return (
    <article className="prose prose-slate dark:prose-invert max-w-none markdown-math">
      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
        {content}
      </ReactMarkdown>
    </article>
  );
}

