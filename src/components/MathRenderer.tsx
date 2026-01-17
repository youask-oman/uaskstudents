"use client";

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
// CSS imported globally in layout.tsx

interface MathRendererProps {
    content?: string | number;
    className?: string;
    inline?: boolean;
    forceMath?: boolean;
}

// =============================================================================
// PREPROCESSING HELPERS (Production-Grade Fixes)
// =============================================================================

/**
 * Fix A: Convert fenced ```latex or ```tex code blocks into $$...$$ 
 */
function convertLatexFencesToMath(md: string): string {
    return md.replace(/```(?:latex|tex)\s*\n([\s\S]*?)```/gi, (_, body) => {
        const inner = String(body).trim();
        return `$$\n${inner}\n$$`;
    });
}

/**
 * Fix A: Auto-wrap LaTeX environments in $$...$$ if not already wrapped
 * This runs REGARDLESS of forceMath - environments always need math mode
 */
function autoWrapLatexEnvironments(md: string): string {
    const hasEnv = /\\begin\{(aligned|align|gather|equation|cases|matrix|pmatrix|bmatrix|vmatrix|array|split)\}/.test(md);
    if (!hasEnv) return md;

    const trimmed = md.trim();
    const alreadyMath =
        (trimmed.startsWith("$$") && trimmed.endsWith("$$")) ||
        (trimmed.startsWith("\\[") && trimmed.endsWith("\\]")) ||
        (trimmed.startsWith("\\(") && trimmed.endsWith("\\)")) ||
        (trimmed.startsWith("$") && trimmed.endsWith("$"));

    return alreadyMath ? md : `$$\n${md}\n$$`;
}

/**
 * Fix C: Wrap simple math tokens like M_n, L^1, x_i that aren't inside math delimiters
 */
function wrapSimpleMathTokens(md: string): string {
    // Split by code/math delimiters to avoid double-wrapping
    const parts = md.split(/(```[\s\S]*?```|`[^`]*`|\$\$[\s\S]*?\$\$|\$[^\$]+\$)/g);
    return parts.map(part => {
        if (
            part.startsWith("```") ||
            part.startsWith("`") ||
            part.startsWith("$")
        ) return part;

        // Wrap tokens like M_n, x_1, L^1, a_{n+1}
        return part.replace(
            /\b([A-Za-z]+(?:_\{[^}]+\}|_[A-Za-z0-9]+|\^\{[^}]+\}|\^[A-Za-z0-9]+)+)\b/g,
            (_, tok) => `$${tok}$`
        );
    }).join("");
}

/**
 * Sanitize common LaTeX artifacts from LLM output
 */
export function sanitizeLatex(input: string): string {
    let clean = input;

    // Fix .textLine patterns
    clean = clean.split('.textLine :').join('. \\text{Line: }');
    clean = clean.split('.textLine:').join('. \\text{Line: }');
    clean = clean.split(').textLine :').join('). \\text{Line: }');
    clean = clean.split(').textLine:').join('). \\text{Line: }');

    // Fix textParabola patterns
    clean = clean.split('.textParabola :').join('. \\text{Parabola: }');
    clean = clean.split('.textParabola:').join('. \\text{Parabola: }');

    // Fix double-escaped backslashes
    clean = clean.split('\\\\text').join('\\text');
    clean = clean.split('\\\\quad').join('\\quad');

    // Fix :; artifact
    clean = clean.split(':;').join(':');

    // Fix missing backslash in text{...}
    clean = clean.replace(/(^|[^\\])text\{/g, '$1\\text{');

    // AGGRESSIVE: Remove malformed $\X$ patterns (single char math that's broken)
    // e.g., "$\f$" => "" or "$\" => ""
    clean = clean.replace(/\$\\[a-zA-Z]?\$/g, '');

    // Remove stray $ followed immediately by backslash and letter (like "$\f'")
    clean = clean.replace(/\$\\([a-zA-Z])/g, '\\$1');

    // Remove trailing $ at end of line/string that's unmatched
    clean = clean.replace(/([^$])\$$/gm, '$1');

    // Remove $ immediately before = or ) when not matched
    clean = clean.replace(/\$([=)])/g, '$1');

    return clean;
}

/**
 * Normalize LaTeX breaks and commands outside math regions
 * Converts \\ to paragraph breaks, \text{...} to plain text, etc.
 */
function normalizeLatexBreaksOutsideMath(input: string): string {
    // Split by protected regions: code fences, inline code, $$...$$, $...$
    const parts = input.split(/(```[\s\S]*?```|`[^`]*`|\$\$[\s\S]*?\$\$|\$[\s\S]*?\$)/g);

    return parts
        .map((part) => {
            // Keep protected parts as-is
            if (
                part.startsWith("```") ||
                part.startsWith("`") ||
                part.startsWith("$$") ||
                part.startsWith("$")
            ) return part;

            // Outside math:
            let s = part;

            // 1) Treat LaTeX linebreaks as paragraph breaks in Markdown
            s = s.replace(/\\\\/g, "\n\n");

            // 2) If model uses \text{Label: } outside math, convert to plain text label
            s = s.replace(/\\text\{([^}]*)\}/g, "$1");

            // 3) Common stray spacing commands outside math
            s = s.replace(/\\quad/g, " ");
            s = s.replace(/\\,/g, " ");
            s = s.replace(/\\ /g, " ");

            // 4) Stray arrows outside math
            s = s.replace(/\\Rightarrow/g, "⇒");
            s = s.replace(/\\Leftarrow/g, "⇐");
            s = s.replace(/\\rightarrow/g, "→");
            s = s.replace(/\\leftarrow/g, "←");

            return s;
        })
        .join("");
}

/**
 * Ensure balanced inline dollar signs (fix missing closing $)
 */
function ensureBalancedInlineDollars(input: string): string {
    // Count unescaped $ (not \$)
    const dollars = (input.match(/(?<!\\)\$/g) || []).length;
    if (dollars % 2 === 1) return input + "$";
    return input;
}

/**
 * Strip inline $ delimiters when content will be rendered as block math
 * Converts "$x^2$" => "x^2" since the whole thing gets wrapped in $$
 */
function stripInlineMathDelimiters(text: string): string {
    // Remove inline $ pairs but preserve $$ pairs
    // First protect $$ pairs
    let clean = text.replace(/\$\$/g, '<<<DOUBLE_DOLLAR>>>');
    // Remove single $ pairs: $content$ => content
    clean = clean.replace(/\$([^$]+)\$/g, '$1');
    // Restore $$ pairs
    clean = clean.replace(/<<<DOUBLE_DOLLAR>>>/g, '$$');
    return clean;
}

/**
 * Inject $...$ around raw LaTeX commands in mixed text (e.g., "Solve \sqrt{x}")
 */
function injectMissingMathDelimiters(text: string): string {
    const parts = text.split(/(`[^`]*`|\$\$[\s\S]*?\$\$|\$[^\$]+\$)/g);

    return parts.map((part) => {
        if (part.startsWith('`') || part.startsWith('$')) return part;

        // Match \cmd possibly followed by {args} groups
        return part.replace(
            /(\\(?!left|right|begin|end)[a-zA-Z]+(?:\{([^{}]|(\{[^{}]*\}))*\})*)+/g,
            (match) => `$${match}$`
        );
    }).join('');
}

/**
 * Unwrap text that was accidentally wrapped in math delimiters
 */
function fixAccidentalMathWrapping(text: string): string {
    const trimmed = text.trim();
    let innerContent = trimmed;
    let isWrapped = false;

    if (trimmed.startsWith('$$') && trimmed.endsWith('$$') && trimmed.length > 4) {
        innerContent = trimmed.slice(2, -2).trim();
        isWrapped = true;
    } else if (trimmed.startsWith('$') && trimmed.endsWith('$') && !trimmed.startsWith('$$') && trimmed.length > 2) {
        innerContent = trimmed.slice(1, -1).trim();
        isWrapped = true;
    }

    if (isWrapped) {
        const spaceCount = (innerContent.match(/\s/g) || []).length;
        const latexCmdCount = (innerContent.match(/\\[a-zA-Z]+/g) || []).length;
        const length = innerContent.length;

        // It's likely plain text if many spaces and few commands
        if (spaceCount >= 3 && latexCmdCount < 2 && length > 20) {
            return innerContent;
        }
    }

    return text;
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function MathRenderer({ content, className = "", inline = false, forceMath = false }: MathRendererProps) {
    if (content === null || content === undefined) return null;
    let text = String(content);

    // Step 1: Convert fenced ```latex blocks to $$...$$
    text = convertLatexFencesToMath(text);

    // Step 2: Auto-wrap LaTeX environments (ALWAYS, regardless of forceMath)
    text = autoWrapLatexEnvironments(text);

    // Step 3: Fix accidentally wrapped text
    text = fixAccidentalMathWrapping(text);

    // Step 4: Wrap simple math tokens like M_n, L^1
    text = wrapSimpleMathTokens(text);

    // Step 5: Inject delimiters for raw math commands (only if NOT forceMath)
    if (!forceMath) {
        text = injectMissingMathDelimiters(text);
    }

    // Step 6: Sanitize LaTeX artifacts
    text = sanitizeLatex(text);

    // Step 7: Normalize LaTeX breaks/commands outside math regions
    text = normalizeLatexBreaksOutsideMath(text);

    // Step 8: Ensure balanced $ delimiters
    text = ensureBalancedInlineDollars(text);

    // Step 9: If forceMath is true and not already wrapped, wrap now
    if (forceMath) {
        const trimmed = text.trim();
        const hasDelimiters =
            (trimmed.startsWith('$$') && trimmed.endsWith('$$')) ||
            (trimmed.startsWith('$') && trimmed.endsWith('$')) ||
            (trimmed.startsWith('\\(') && trimmed.endsWith('\\)')) ||
            (trimmed.startsWith('\\[') && trimmed.endsWith('\\]'));

        if (!hasDelimiters) {
            // Strip inline $ delimiters since we'll wrap in $$ anyway
            text = stripInlineMathDelimiters(text);
            // Check if content requires block mode
            const requiresBlock = /\\begin\{|\\\\/.test(text);
            if (requiresBlock || !inline) {
                text = `$$${text}$$`;
            } else {
                text = `$${text}$`;
            }
        }
    }

    // Use correct wrapper element based on mode
    const Wrapper: any = inline ? "span" : "div";

    return (
        <Wrapper className={`math-renderer markdown-math ${className} ${inline ? "inline-block" : "block"}`}>
            <ReactMarkdown
                remarkPlugins={[remarkMath]}
                rehypePlugins={[
                    [rehypeKatex, { throwOnError: false, strict: 'ignore' }]
                ]}
                components={{
                    // Only override p to span in inline mode
                    p: ({ children, ...props }) => {
                        if (inline) {
                            return <span {...props}>{children}{" "}</span>;
                        }
                        return <p {...props}>{children}</p>;
                    },
                }}
            >
                {text}
            </ReactMarkdown>
        </Wrapper>
    );
}
