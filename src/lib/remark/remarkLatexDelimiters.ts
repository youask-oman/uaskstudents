type MdastNode = {
  type: string;
  value?: string;
  children?: MdastNode[];
};

const TEX_COMMAND_RE =
  /\\(frac|sqrt|approx|implies|quad|left|right|begin|end|sum|int|lim|cdot|times|alpha|beta|gamma|theta|pi|sin|cos|tan|log|ln)\b/;

function isShortNonMathBracketToken(value: string): boolean {
  const v = value.trim();
  if (!v) return true;
  if (/^[a-zA-Z]$/.test(v)) return true;
  if (/^\d{1,2}$/.test(v)) return true;
  return false;
}

function looksLikeBracketMath(value: string): boolean {
  const v = value.trim();
  if (!v) return false;
  if (isShortNonMathBracketToken(v)) return false;
  if (TEX_COMMAND_RE.test(v)) return true;

  const hasEquals = v.includes("=");
  const hasMathOperator = /[\^_+\-*/]/.test(v);
  return hasEquals && hasMathOperator;
}

function looksLikeParenMath(value: string): boolean {
  const v = value.trim();
  if (!v) return false;
  if (v.length <= 2) return false;
  if (TEX_COMMAND_RE.test(v)) return true;
  if (/[\^_]/.test(v)) return true;
  if (/^[A-Za-z](?:'+)?\([^)]+\)$/.test(v)) return true; // f(x), f'(x), g''(t)
  if (/[=<>]/.test(v) && /[A-Za-z0-9]/.test(v)) return true;
  if (/\b[a-zA-Z]\s*[+\-*/]\s*\d+/.test(v)) return true;
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
    { regex: /\\\[((?:.|\n)*?)\\\]/g, id: "escaped_block", kind: "block" },
    { regex: /\\\((.+?)\\\)/g, id: "escaped_inline", kind: "inline" },
    {
      regex: /\[([^\[\]\n]+?)\]/g,
      id: "bracket",
      kind: "inline",
      accept: (tex) => looksLikeBracketMath(tex),
    },
    {
      regex: /\(([^()\n]+?)\)/g,
      id: "paren",
      kind: "inline",
      accept: (tex) => looksLikeParenMath(tex),
    },
    {
      regex: /\(\s*([A-Za-z](?:'+)?\([^)]+\))\s*\)/g,
      id: "paren_wrapped_fn",
      kind: "inline",
    },
  ];

  let best: null | { start: number; end: number; kind: "inline" | "block"; tex: string } = null;

  for (const pattern of patterns) {
    pattern.regex.lastIndex = from;
    const match = pattern.regex.exec(text);
    if (!match || match.index < from) continue;
    const tex = String(match[1] || "").trim();
    if (!tex) continue;
    if (pattern.accept && !pattern.accept(tex)) continue;

    let kind = pattern.kind;
    if (pattern.id === "bracket" && (tex.includes("\\begin{") || tex.length > 60)) {
      kind = "block";
    }

    const candidate = { start: match.index, end: match.index + match[0].length, kind, tex };
    if (!best || candidate.start < best.start) best = candidate;
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
      nodes.push({ type: "math", value: hit.tex });
    } else {
      nodes.push({ type: "inlineMath", value: hit.tex });
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
