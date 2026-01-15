
"use client";

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

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


export default function MathRenderer({ content, className = "", inline = false, forceMath = false }: MathRendererProps) {
    if (content === null || content === undefined) return null;
    let text = String(content);

    // === PRE-PROCESSING: Strip math delimiters from plain English sentences ===
    // If content is wrapped in $...$ or $$...$$ but is primarily English text, remove delimiters.
    // This fixes backend outputs like "$$Graph the two functions y = x^2$$" being rendered as math.
    const trimmed = text.trim();
    let innerContent = trimmed;
    let wasWrapped = false;

    // Check for and strip outer math delimiters
    if (trimmed.startsWith('$$') && trimmed.endsWith('$$')) {
        innerContent = trimmed.slice(2, -2).trim();
        wasWrapped = true;
    } else if (trimmed.startsWith('$') && trimmed.endsWith('$') && !trimmed.startsWith('$$')) {
        innerContent = trimmed.slice(1, -1).trim();
        wasWrapped = true;
    }

    if (wasWrapped) {
        // Heuristic: If inner content has 3+ words separated by spaces AND no LaTeX commands (backslash), it's text.
        const wordCount = innerContent.split(/\s+/).filter(w => w.length > 0).length;
        const hasLatexCommands = innerContent.includes('\\');
        const startsWithText = /^[A-Z][a-z]/.test(innerContent); // Starts with capital letter (sentence)

        if (wordCount >= 3 && !hasLatexCommands && startsWithText) {
            // This is plain English wrapped in math delimiters - strip them!
            text = innerContent;
        }
    }

    // Sanitize input
    text = sanitizeLatex(text);

    // Auto-detect if we should force BLOCK mode despite "inline" prop
    // If output contains LaTeX newlines (\\) or environment starts (\begin), must be block.
    const hasBlockTriggers = text.includes("\\\\") || text.includes("\\begin{");
    const shouldUseBlock = hasBlockTriggers || !inline;

    if (forceMath) {
        // cleanup potential existing delimiters to avoid double wrapping
        const trimmed = text.trim();
        const hasDelimiters = (trimmed.startsWith('$') && trimmed.endsWith('$')) ||
            (trimmed.startsWith('\\(') && trimmed.endsWith('\\)')) ||
            (trimmed.startsWith('\\[') && trimmed.endsWith('\\]'));

        if (!hasDelimiters) {
            // Apply appropriate wrappers
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
        <span className={`math-renderer ${className} ${inline ? 'inline-block' : 'block'}`}>
            <ReactMarkdown
                remarkPlugins={[remarkMath]}
                rehypePlugins={[rehypeKatex]}
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
