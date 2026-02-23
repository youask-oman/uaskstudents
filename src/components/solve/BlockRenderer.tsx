"use client";

import MarkdownMathContent from "@/components/math/MarkdownMathContent";
import UnifiedMathRenderer from "@/components/math/UnifiedMathRenderer";
import type { PlaybackBlock } from "@/lib/playback/useRenderPlayback";

export default function BlockRenderer({ block }: { block: PlaybackBlock }) {
  if (block.kind === "math") {
    return (
      <div style={{ margin: "6px 0" }}>
        <UnifiedMathRenderer content={String(block.latex || "")} mode={block.display ? "block" : "inline"} />
      </div>
    );
  }
  return (
    <div style={{ margin: "4px 0" }}>
      <MarkdownMathContent content={String(block.text || "")} />
    </div>
  );
}
