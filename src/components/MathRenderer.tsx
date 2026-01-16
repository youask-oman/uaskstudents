
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
    forceMath?: boolean; // If true, wraps content in delimiters if missing
}

// Export for unit testing
export function sanitizeLatex(input: string): string {
    let clean = input;

    // STEP 1: Direct string replacements for EXACT known artifacts
    // Using split().join() is more reliable than regex for exact matches

    // Fix .textLine : patterns (with various spacing)
    clean = clean.split('.textLine :').join('. \\text{Line: }');
    clean = clean.split('.textLine:').join('. \\text{Line: }');
    clean = clean.split(').textLine :').join('). \\text{Line: }');
    clean = clean.split(').textLine:').join('). \\text{Line: }');
    clean = clean.split(')textLine :').join(') \\text{Line: }');
    clean = clean.split(')textLine:').join(') \\text{Line: }');

    // Fix textParabola patterns
    clean = clean.split('.textParabola :').join('. \\text{Parabola: }');
    clean = clean.split('.textParabola:').join('. \\text{Parabola: }');
    clean = clean.split(').textParabola :').join('). \\text{Parabola: }');
    clean = clean.split(').textParabola:').join('). \\text{Parabola: }');

    // Fix textPlot patterns
    clean = clean.split('.textPlot :').join('. \\text{Plot: }');
    clean = clean.split('.textPlot:').join('. \\text{Plot: }');

    // Fix remaining standalone textLine, textParabola at word boundaries
    clean = clean.split(' textLine :').join(' \\text{Line: }');
    clean = clean.split(' textLine:').join(' \\text{Line: }');
    clean = clean.split(' textParabola :').join(' \\text{Parabola: }');
    clean = clean.split(' textParabola:').join(' \\text{Parabola: }');

    // STEP 2: Fix double-escaped backslashes
    clean = clean.split('\\\\text').join('\\text');
    clean = clean.split('\\\\quad').join('\\quad');

    // STEP 3: Fix :; artifact
    clean = clean.split(':;').join(':');

    // STEP 4: Fix missing backslash in text{...}
    // Use regex for this since we need negative lookbehind behavior
    clean = clean.replace(/(^|[^\\])text\{/g, '$1\\text{');

    // STEP 5: General CamelCase text* patterns (regex needed for flexibility)
    clean = clean.replace(/(^|[^a-zA-Z\\])text([A-Z][a-z]+(?:[A-Z][a-z]*)*)/g, (match, prefix, camelText) => {
        const spaced = camelText
            .replace(/([A-Z])/g, ' $1')
            .trim()
            .replace(/\s+/g, ' ');
        return `${prefix}\\text{${spaced} }`;
    });

    // STEP 6: Add line break before \text{Line to separate from Parabola
    clean = clean.split('). \\text{Line').join('). \\\\ \\text{Line');

    return clean;
}

// Additional helper to split multi-part solutions into separate renderable lines
export function splitSolutionIntoLines(input: string): string[] {
    // First sanitize
    const sanitized = sanitizeLatex(input);

    // Split on common separators: \\, newlines, or pattern like "). \text{Line"
    const lines = sanitized
        .split(/(?:\\\\\s*)|(?:\n)|(?:\)\.\s*(?=\\\\?text\{(?:Line|Parabola|Plot)))/gi)
        .map(line => line.trim())
        .filter(line => line.length > 0);

    return lines.length > 0 ? lines : [sanitized];
}

// Helper to detect and fix accidental math wrapping on plain text
function fixAccidentalMathWrapping(text: string): string {
    const trimmed = text.trim();

    // Check for "Paragraph Wrapped in Math" e.g. "$Radicals require...$" 
    // Logic: Starts/Ends with $, but looks like text inside.
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
        // Heuristic: If it has multiple spaces and minimal LaTeX syntax, it's text.
        // If > 20 chars, > 3 spaces, and few backslashes, unwrap it.
        const spaceCount = (innerContent.match(/\s/g) || []).length;
        const latexCmdCount = (innerContent.match(/\\[a-zA-Z]+/g) || []).length;
        const length = innerContent.length;

        // "Radicals require their radicands..." has 0 commands, many spaces.
        if (spaceCount >= 3 && latexCmdCount < 2 && length > 20) {
            // It's likely text. Return unwrapped content.
            return innerContent;
        }
    }

    return text;
}


// Helper: Auto-wrap raw LaTeX commands in $...$ if they are missing delimiters
// Handles up to 1 level of nested braces, e.g. \sqrt{x+3} or \frac{1}{2}
function injectMissingMathDelimiters(text: string): string {
    // Split by code blocks or existing math to avoid double-wrapping
    // Regex matches `code`, $$math$$, or $math$
    const parts = text.split(/(`[^`]*`|\$\$[\s\S]*?\$\$|\$[\s\S]*?\$)/g);

    return parts.map((part) => {
        // If part is a code block or already math, return as-is
        if (part.startsWith('`') || part.startsWith('$')) return part;

        // Otherwise, look for raw LaTeX patterns
        // Regex: matches \cmd (excluding left/right/begin/end) possibly followed by {args} with up to 1 level of nesting
        // We exclude structural commands like \left, \right because wrapping them individually breaks the pair.
        return part.replace(
            /(\\(?!left|right|begin|end)[a-zA-Z]+(?:\{([^{}]|(\{[^{}]*\}))*\})?)+/g,
            (match) => `$${match}$`
        );
    }).join('');
}


export default function MathRenderer({ content, className = "", inline = false, forceMath = false }: MathRendererProps) {
    if (content === null || content === undefined) return null;
    let text = String(content);

    // DEBUG LOG (Dev Only) - Check spacing/content
    if (process.env.NODE_ENV === 'development' && text.length > 0) {
        // console.log(`[MathRenderer] Raw input (${text.length}):`, text.slice(0, 100));
    }

    // 1. Fix Accidental Wrapping (C3) - Unwrap "Text wrapped in $$"
    text = fixAccidentalMathWrapping(text);

    // 2. Inject Delimiters for Raw Math (Fixes "Solve \sqrt{x}" -> "Solve $\sqrt{x}$")
    // CRITICAL: Only do this for mixed text! if forceMath is true, we expect the whole string to be math (or we wrap it all later).
    // Injecting $ inside a string we plan to wrap in $$ creates invalid double-nested math.
    if (!forceMath) {
        text = injectMissingMathDelimiters(text);
    }

    // 3. Sanitize Artifacts
    text = sanitizeLatex(text);

    // Auto-detect if we should force BLOCK mode despite "inline" prop
    const hasBlockTriggers = text.includes("\\\\") || text.includes("\\begin{");
    const shouldUseBlock = hasBlockTriggers || !inline;

    if (forceMath) {
        // cleanup potential existing delimiters to avoid double wrapping
        const trimmed = text.trim();
        // Only wrap if NOT already wrapped
        const hasDelimiters = (trimmed.startsWith('$') && trimmed.endsWith('$')) ||
            (trimmed.startsWith('\\(') && trimmed.endsWith('\\)')) ||
            (trimmed.startsWith('\\[') && trimmed.endsWith('\\]'));

        if (!hasDelimiters) {
            // Logic: If it looks like text (has spaces, no math symbols), maybe DON'T force wrap?
            // But forceMath=true implies caller knows better. 
            // We'll wrap it.
            if (shouldUseBlock && hasBlockTriggers) {
                text = `$$${text}$$`;
            } else if (inline) {
                text = `$${text}$`;
            } else {
                // Default to block if not explicitly inline
                text = `$$${text}$$`;
            }
        }
    }

    return (
        <span className={`math-renderer markdown-math ${className} ${inline ? 'inline-block' : 'block'}`}>
            <ReactMarkdown
                remarkPlugins={[remarkMath]}
                rehypePlugins={[
                    [rehypeKatex, { throwOnError: false, strict: 'ignore' }]
                ]}
                components={{
                    // Override p to span to avoid block breaking in inline contexts
                    p: ({ node, ...props }) => <span {...props} className="maybe-math" />
                }}
            >
                {text}
            </ReactMarkdown>
        </span>
    );
}
