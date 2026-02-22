"use client";

import { useEffect, useMemo, useState } from "react";
import MarkdownMathContent from "@/components/math/MarkdownMathContent";
import { generateStressCases } from "@/lib/mathjax/stressCases";

const intro = `
# Math SVG Stress Test (1000 Cases)

Inline samples from bad model format:
First: [ f'(x)=3x^2-12x+9 ] and [ 3(x^2-4x+3)=0 \\implies 3(x-1)(x-3)=0 ]

Negative controls (must remain unchanged):
- [x] task list item
- Reference [1]

\`\`\`js
const price = "$5";
const expr = "x$y";
\`\`\`
`;

export default function MathSvgStressPage() {
  const cases = useMemo(() => generateStressCases(1000, 20260222), []);
  const [visibleCount, setVisibleCount] = useState(120);

  useEffect(() => {
    if (visibleCount >= cases.length) return;
    const timer = window.setInterval(() => {
      setVisibleCount((prev) => Math.min(cases.length, prev + 80));
    }, 120);
    return () => window.clearInterval(timer);
  }, [cases.length, visibleCount]);

  const lines = cases.slice(0, visibleCount).map((c) => `${c.id}. ${c.bracketWrapped}`).join("\n\n");
  const markdown = `${intro}\n\n## Rendered Cases (${visibleCount}/${cases.length})\n\n${lines}`;

  return (
    <main style={{ maxWidth: 980, margin: "0 auto", padding: "24px 20px" }}>
      <MarkdownMathContent content={markdown} />
    </main>
  );
}

