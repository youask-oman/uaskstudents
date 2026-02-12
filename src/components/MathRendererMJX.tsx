"use client";

import React from "react";
import { MathJax, MathJaxContext } from "better-react-mathjax";
import { convertLatexFencesToMath, normalizePlainSqrt, escapeUnmatchedRightDelimiters } from "./MathUtils";

export interface MathRendererMJXProps {
  content?: string | number;
  inline?: boolean;
  className?: string;
  dynamic?: boolean;
  hideUntilTypeset?: "first" | "every";
}

const MATHJAX_CONTEXT_CONFIG = {
  loader: { load: ["input/tex", "output/svg"] },
  tex: {
    inlineMath: [["\\(", "\\)"], ["$", "$"]],
    displayMath: [["\\[", "\\]"], ["$$", "$$"]],
    processEscapes: true,
    packages: { "[+]": ["base", "ams", "newcommand", "noundefined"] },
  },
  svg: { fontCache: "local" },
};

const isEscaped = (text: string, index: number) => {
  let backslashes = 0;
  let cursor = index - 1;
  while (cursor >= 0 && text[cursor] === "\\") {
    backslashes += 1;
    cursor -= 1;
  }
  return backslashes % 2 === 1;
};

const findDelimiter = (text: string, delimiter: string, fromIndex: number) => {
  let location = text.indexOf(delimiter, fromIndex);
  while (location !== -1) {
    if (!isEscaped(text, location)) {
      return location;
    }
    location = text.indexOf(delimiter, location + 1);
  }
  return -1;
};

const convertDisplayMath = (text: string) => {
  let cursor = 0;
  let output = "";

  while (cursor < text.length) {
    const start = findDelimiter(text, "$$", cursor);
    if (start === -1) {
      output += text.slice(cursor);
      break;
    }

    output += text.slice(cursor, start);
    const closing = findDelimiter(text, "$$", start + 2);
    if (closing === -1) {
      output += "\\$\\$";
      cursor = start + 2;
      continue;
    }

    const block = text.slice(start + 2, closing);
    output += `\\[\n${block}\n\\]`;
    cursor = closing + 2;
  }

  return output;
};

const looksLikeMath = (candidate: string) => {
  const trimmed = candidate.trim();
  if (!trimmed) return false;

  const hasCommand = /\\[a-zA-Z]+/.test(trimmed);
  const hasOperator = /[=+\-*/^_<>±≈≠≥≤√∞]/.test(trimmed);
  const hasGreek = /[αβγδεζηθικλμνξπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΠΡΣΤΥΦΧΨΩ]/.test(trimmed);
  const hasAccented = /[a-zA-Z]\u0304/.test(trimmed); // x-bar

  const compactLength = trimmed.replace(/\s+/g, "").length;
  const lettersOnly = /^[\da-zA-Z\s]+$/.test(trimmed);

  if (hasCommand || hasOperator || hasGreek || hasAccented) return true;
  if (lettersOnly && compactLength <= 6) return true;
  return false;
};

const convertInlineMath = (text: string) => {
  let cursor = 0;
  let output = "";

  while (cursor < text.length) {
    const start = findDelimiter(text, "$", cursor);
    if (start === -1) {
      output += text.slice(cursor);
      break;
    }

    if (text[start + 1] === "$") {
      output += text.slice(cursor, start + 1);
      cursor = start + 1;
      continue;
    }

    output += text.slice(cursor, start);
    const closing = findDelimiter(text, "$", start + 1);
    if (closing === -1) {
      output += "\\$";
      cursor = start + 1;
      continue;
    }

    const inner = text.slice(start + 1, closing);
    if (looksLikeMath(inner)) {
      output += `\\(${inner}\\)`;
    } else {
      output += `\\$${inner}\\$`;
    }
    cursor = closing + 1;
  }

  return output;
};

const commandRequiresArgument = new Set([
  "frac",
  "dfrac",
  "tfrac",
  "sqrt",
  "binom",
  "text",
  "textcolor",
  "color",
  "overline",
  "underline",
  "vec",
]);

const noArgCommands = new Set([
  "neq",
  "le",
  "leq",
  "ge",
  "geq",
  "lt",
  "gt",
  "times",
  "cdot",
  "pm",
  "mp",
  "div",
  "infty",
  "to",
  "rightarrow",
  "leftarrow",
  "Rightarrow",
  "Leftarrow",
  "iff",
  "approx",
  "sim",
  "alpha",
  "beta",
  "gamma",
  "delta",
  "epsilon",
  "zeta",
  "eta",
  "theta",
  "iota",
  "kappa",
  "lambda",
  "mu",
  "nu",
  "xi",
  "pi",
  "rho",
  "sigma",
  "tau",
  "upsilon",
  "phi",
  "chi",
  "psi",
  "omega",
]);

const relationCommands = new Set([
  "neq",
  "le",
  "leq",
  "ge",
  "geq",
  "lt",
  "gt",
  "approx",
  "sim",
  "to",
  "rightarrow",
  "leftarrow",
  "Rightarrow",
  "Leftarrow",
]);

const parseGroup = (text: string, start: number, openChar: string, closeChar: string) => {
  let depth = 0;
  let cursor = start;
  while (cursor < text.length) {
    const ch = text[cursor];
    if (ch === openChar) depth += 1;
    if (ch === closeChar) {
      depth -= 1;
      if (depth === 0) {
        return cursor + 1;
      }
    }
    cursor += 1;
  }
  return -1;
};

const consumeScripts = (text: string, start: number) => {
  let cursor = start;
  while (cursor < text.length) {
    const next = text[cursor];
    if (next !== "^" && next !== "_") break;
    cursor += 1;
    if (text[cursor] === "{") {
      const end = parseGroup(text, cursor, "{", "}");
      if (end === -1) return cursor;
      cursor = end;
      continue;
    }
    cursor += 1;
  }
  return cursor;
};

const wrapBareLatexFragments = (text: string) => {
  const parts = text.split(/(```[\s\S]*?```|`[^`]*`|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\))/g);

  return parts
    .map((part) => {
      if (
        part.startsWith("```") ||
        part.startsWith("`") ||
        part.startsWith("\\[") ||
        part.startsWith("\\(")
      ) {
        return part;
      }

      let output = "";
      let cursor = 0;

      while (cursor < part.length) {
        const start = part.indexOf("\\", cursor);
        if (start === -1) {
          output += part.slice(cursor);
          break;
        }

        output += part.slice(cursor, start);
        if (start + 1 >= part.length || !/[a-zA-Z]/.test(part[start + 1])) {
          output += part[start];
          cursor = start + 1;
          continue;
        }

        let end = start + 1;
        while (end < part.length && /[a-zA-Z]/.test(part[end])) {
          end += 1;
        }

        const command = part.slice(start + 1, end);
        let segmentEnd = end;

        if (command === "begin") {
          const braceStart = part.indexOf("{", end);
          if (braceStart === end) {
            const braceEnd = parseGroup(part, braceStart, "{", "}");
            if (braceEnd !== -1) {
              const envName = part.slice(braceStart + 1, braceEnd - 1);
              const endTag = `\\end{${envName}}`;
              const endIndex = part.indexOf(endTag, braceEnd);
              if (endIndex !== -1) {
                const envSegment = part.slice(start, endIndex + endTag.length);
                output += `\\[${envSegment}\\]`;
                cursor = endIndex + endTag.length;
                continue;
              }
            }
          }
        }

        let scan = segmentEnd;
        while (scan < part.length && part[scan] === " ") scan += 1;

        if (scan < part.length && part[scan] === "[") {
          const optEnd = parseGroup(part, scan, "[", "]");
          if (optEnd !== -1) {
            segmentEnd = optEnd;
            scan = segmentEnd;
          }
        }

        scan = segmentEnd;
        while (scan < part.length && part[scan] === " ") scan += 1;

        if (scan < part.length && part[scan] === "{") {
          while (scan < part.length && part[scan] === "{") {
            const groupEnd = parseGroup(part, scan, "{", "}");
            if (groupEnd === -1) break;
            segmentEnd = groupEnd;
            scan = segmentEnd;
            while (scan < part.length && part[scan] === " ") scan += 1;
          }
        } else if (commandRequiresArgument.has(command)) {
          output += part.slice(start, segmentEnd);
          cursor = segmentEnd;
          continue;
        }

        segmentEnd = consumeScripts(part, segmentEnd);

        if (relationCommands.has(command)) {
          let rhsStart = segmentEnd;
          while (rhsStart < part.length && part[rhsStart] === " ") rhsStart += 1;
          if (rhsStart < part.length) {
            if (part[rhsStart] === "{") {
              const rhsEnd = parseGroup(part, rhsStart, "{", "}");
              if (rhsEnd !== -1) segmentEnd = rhsEnd;
            } else if (/[0-9a-zA-Z]/.test(part[rhsStart])) {
              segmentEnd = rhsStart + 1;
            }
          }
        }

        if (noArgCommands.has(command) || segmentEnd > end) {
          const segment = part.slice(start, segmentEnd);
          output += `\\(${segment}\\)`;
          cursor = segmentEnd;
          continue;
        }

        output += part.slice(start, end);
        cursor = end;
      }

      return output;
    })
    .join("");
};

/**
 * Auto-detect and wrap bare math expressions that lack LaTeX delimiters.
 * Uses a single-pass approach to avoid double-wrapping.
 */
const wrapBareMathExpressions = (text: string) => {
  // Skip if already inside LaTeX delimiters or code blocks
  const parts = text.split(/(```[\s\S]*?```|`[^`]*`|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\))/g);

  return parts
    .map((part) => {
      if (
        part.startsWith("```") ||
        part.startsWith("`") ||
        part.startsWith("\\[") ||
        part.startsWith("\\(")
      ) {
        return part;
      }

      let output = part;

      // Only apply if no existing LaTeX delimiters are detected in this segment
      if (!output.includes("\\(") && !output.includes("\\[")) {
        // Step 1: Normalize symbols to LaTeX commands
        output = output
          .replace(/√\s*([0-9a-zA-Z]+)/g, "\\sqrt{$1}")
          .replace(/x\u0304/g, "\\bar{x}")
          .replace(/±/g, "\\pm")
          .replace(/≈/g, "\\approx")
          .replace(/≠/g, "\\neq")
          .replace(/≥/g, "\\ge")
          .replace(/≤/g, "\\le")
          .replace(/σ/g, "\\sigma")
          .replace(/α/g, "\\alpha")
          .replace(/μ/g, "\\mu");

        // Step 2: Wrap all standard LaTeX commands in \(\)
        // Match \command or \command{...}
        output = output.replace(/\\[a-z]+(?:\{[^}]*\})*/g, (m) => `\\(${m}\\)`);

        // Step 3: Wrap common equations (e.g., n = 725, x = 1.2)
        // Avoid double wrapping if already inside a delimiter
        output = output.replace(/\b([a-zA-Z])\s*=\s*(-?\d+(?:\.\d+)?)\b/g, (m) => {
          if (output.includes(`\\(${m}\\)`)) return m;
          return `\\(${m}\\)`;
        });

        // Step 4: Wrap coordinate points
        output = output.replace(
          /\((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)(?=[.,;:!?\s]|$)/g,
          "\\(($1, $2)\\)"
        );

        // Step 5: Wrap complex expressions containing math operators (e.g. CI = ...)
        output = output.replace(/([a-zA-Z]{1,2}\s*=\s*[^,.;:!?\n]+)/g, (m) => {
          if (m.includes("\\(")) return m;
          if (looksLikeMath(m)) return `\\(${m.trim()}\\)`;
          return m;
        });

        // Step 6: Fix double-wrapping artifacts
        output = output.replace(/\\\(\s*\\\(/g, "\\(").replace(/\\\)\s*\\\)/g, "\\)");
      }

      return output;
    })
    .join("");
};

export const prepareMathJaxContent = (content?: string | number) => {
  if (content === null || content === undefined) return "";
  let text = String(content);
  text = convertLatexFencesToMath(text);
  text = convertDisplayMath(text);
  text = convertInlineMath(text);
  text = normalizePlainSqrt(text);
  text = wrapBareMathExpressions(text);
  text = wrapBareLatexFragments(text);
  text = escapeUnmatchedRightDelimiters(text);
  return text;
};

export default function MathRendererMJX({
  content,
  inline = false,
  className = "",
  dynamic = true,
  hideUntilTypeset = "first",
}: MathRendererMJXProps) {
  const prepared = React.useMemo(() => prepareMathJaxContent(content), [content]);
  if (!prepared) return null;

  const Wrapper: React.ElementType = inline ? "span" : "div";

  return (
    <Wrapper
      className={`math-renderer-mjx markdown-math ${className} ${inline ? "inline-block" : "block"}`}
      style={{ whiteSpace: inline ? "normal" : "pre-wrap" }}
    >
      <MathJaxContext version={3} config={MATHJAX_CONTEXT_CONFIG}>
        <MathJax dynamic={dynamic} hideUntilTypeset={hideUntilTypeset} renderMode="post">
          {prepared}
        </MathJax>
      </MathJaxContext>
    </Wrapper>
  );
}
