"use client";

import MarkdownMathContent from "@/components/math/MarkdownMathContent";

type Props = {
  content: string;
};

export function ChatFinalMessage({ content }: Props) {
  return (
    <div className="prose prose-slate max-w-none break-words leading-7 whitespace-normal">
      <MarkdownMathContent content={content} />
    </div>
  );
}

