type MdastNode = {
  type: string;
  value?: string;
  children?: MdastNode[];
  data?: {
    hName?: string;
    hProperties?: Record<string, any>;
  };
};

const TEX_COMMAND_RE =
  /\\(frac|sqrt|approx|implies|quad|left|right|begin|end|sum|int|lim|cdot|times|alpha|beta|gamma|theta|pi|sin|cos|tan|log|ln|boxed|text|mathrm|mathbf|operatorname|pm|mp|leq|geq|neq|infty|partial|nabla|to)\b/;

function isShortNonMathBracketToken(value: string): boolean {
  const v = value.trim();
  if (!v) return true;
  if (/^[a-zA-Z]$/.test(v)) return true;
  if (/^\d{1,2}$/.test(v)) return true;
  return false;
}

const PROSE_WORDS_RE = /\b(and|or|with|for|such|that|the|is|are|was|were|has|have|can|will|should|must|then|therefore|because|from|here|each|this|using|method|methods|numerical|approximate|find|found|calculate|calculator|result|between|above|below|next|then|finally|classify|critical|points|occur|where|derivative|sign|change|confirm|check|around|interval|plot|graph|curve|marked|distinct|markers|legend|words|cubic|polynomial|local|maximum|minimum|intercepts|roots|step|steps|answer)\b/i;

function looksLikeBracketMath(value: string): boolean {
  const v = value.trim();
  if (!v) return false;
  if (isShortNonMathBracketToken(v)) return false;

  // If it contains explicit TeX commands, it's very likely math
  if (TEX_COMMAND_RE.test(v)) return true;

  // Reject if it contains common prose words (helps prevent connected words issue)
  if (PROSE_WORDS_RE.test(v)) return false;

  // Count plain words to avoid capturing prose
  const plainWords = (v.match(/\b[A-Za-z]{3,}\b/g) || []).length;
  if (plainWords >= 2) return false;

  // Catch expressions like x = 3, y > 5, f'(x), etc.
  if (/[=<>]/.test(v)) return true;
  // Catch simple variable and operator patterns
  if (/[\^_+\-*/]/.test(v)) return true;
  // Catch function notation
  if (/[a-zA-Z]['"]*\(.*?\)[\s=]*/.test(v)) return true;

  return false;
}

function looksLikeParenMath(value: string): boolean {
  const v = value.trim();
  if (!v) return false;
  if (v.length <= 2) return false;

  // If it contains explicit TeX commands, it's very likely math
  if (TEX_COMMAND_RE.test(v)) return true;

  // Reject if it contains common prose words
  if (PROSE_WORDS_RE.test(v)) return false;

  // Count plain words to avoid capturing prose
  const plainWords = (v.match(/\b[A-Za-z]{3,}\b/g) || []).length;
  if (plainWords >= 2) return false;

  if (/[\^_]/.test(v)) return true;

  // Catch comparisons/operators: =, >, <, +, -, *, /
  if (/[=<>+\-*/]/.test(v)) return true;
  // Catch function notation/derivatives: f(x), f'(x), f''(x), etc.
  if (/[a-zA-Z][^()\n]*\(.*?\)/.test(v)) return true;

  return false;
}

function nextMatch(text: string, from: number): null | {
  start: number;
  end: number;
  kind: "inline" | "block";
  tex: string;
} {
  const patterns: Array<{
    regex: RegExp;
    id: "escaped_block" | "escaped_inline" | "bracket" | "paren" | "paren_wrapped_fn";
    kind: "inline" | "block";
    accept?: (tex: string) => boolean;
  }> = [
      {
        regex: /\\\[((?:.|\n)*?)\\\]/g,
        id: "escaped_block",
        kind: "block",
        accept: (tex) => looksLikeBracketMath(tex),
      },
      {
        regex: /\\\((.+?)\\\)/g,
        id: "escaped_inline",
        kind: "inline",
        accept: (tex) => looksLikeParenMath(tex),
      },
      {
        regex: /\\boxed\{((?:.|\n)+?)\}/g,
        id: "escaped_inline",
        kind: "inline",
        accept: (tex) => looksLikeBracketMath(tex),
      },
      {
        regex: /\[((?:.|\n)+?)\]/g,
        id: "bracket",
        kind: "inline",
        accept: (tex) => looksLikeBracketMath(tex),
      },
      {
        // Updated to allow balanced nested parens, e.g. (f(x) = 0)
        // Also allowing newlines for more robust matching in streaming content
        regex: /\(([^()\n]+(?:\([^()]*\)[^()]*)*)\)/g,
        id: "paren",
        kind: "inline",
        accept: (tex) => looksLikeParenMath(tex),
      },
    ];

  let best: null | { start: number; end: number; kind: "inline" | "block"; tex: string } = null;

  for (const pattern of patterns) {
    pattern.regex.lastIndex = from;
    let match = pattern.regex.exec(text);

    while (match && match.index >= from) {
      const tex = String(match[1] || "").trim();
      if (tex && (!pattern.accept || pattern.accept(tex))) {
        let kind = pattern.kind;
        if (pattern.id === "bracket" && (tex.includes("\\begin{") || tex.includes("\\newline") || tex.includes("\\cases") || tex.includes("\\matrix") || tex.includes("\n") || tex.length > 60)) {
          kind = "block";
        }

        const candidate = { start: match.index, end: match.index + match[0].length, kind, tex };
        if (!best || candidate.start < best.start || (candidate.start === best.start && candidate.end > best.end)) {
          best = candidate;
        }
        // Found a valid match for this pattern, move to next pattern
        break;
      }
      // Not accepted, try next match of the same pattern
      match = pattern.regex.exec(text);
    }
  }

  return best;
}

function textToNodes(value: string): MdastNode[] {
  const nodes: MdastNode[] = [];
  let cursor = 0;

  while (cursor < value.length) {
    const hit = nextMatch(value, cursor);
    if (!hit) {
      const tail = value.slice(cursor);
      if (tail) nodes.push({ type: "text", value: tail });
      break;
    }

    if (hit.start > cursor) {
      const head = value.slice(cursor, hit.start);
      if (head) nodes.push({ type: "text", value: head });
    }

    if (hit.kind === "block") {
      nodes.push({
        type: "math",
        value: hit.tex,
        data: {
          hName: "latex-math-block",
          hProperties: { tex: hit.tex },
        },
      });
    } else {
      nodes.push({
        type: "inlineMath",
        value: hit.tex,
        data: {
          hName: "latex-math-inline",
          hProperties: { tex: hit.tex },
        },
      });
    }

    cursor = hit.end;
  }

  return nodes;
}

function transformNode(node: MdastNode): void {
  const children = Array.isArray(node.children) ? node.children : null;
  if (!children || children.length === 0) return;

  const skipChildren = node.type === "code" || node.type === "inlineCode";
  if (skipChildren) return;

  const nextChildren: MdastNode[] = [];
  for (const child of children) {
    if (child.type === "text" && typeof child.value === "string") {
      const expanded = textToNodes(child.value);
      nextChildren.push(...expanded);
    } else {
      transformNode(child);
      nextChildren.push(child);
    }
  }
  node.children = nextChildren;
}

export default function remarkLatexDelimiters() {
  return (tree: unknown) => {
    if (!tree || typeof tree !== "object") return;
    transformNode(tree as MdastNode);
  };
}
