
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

    // 0. MOST AGGRESSIVE: Direct string replacement for known artifacts
    // These are the EXACT patterns seen in screenshots
    clean = clean.replace(/\.textLine\s*:\s*/gi, '. \\text{Line: }');
    clean = clean.replace(/\)\.textLine\s*:\s*/gi, '). \\text{Line: }');
    clean = clean.replace(/\)textLine\s*:\s*/gi, ') \\text{Line: }');
    clean = clean.replace(/\.textParabola\s*:\s*/gi, '. \\text{Parabola: }');
    clean = clean.replace(/\)\.textParabola\s*:\s*/gi, '). \\text{Parabola: }');
    clean = clean.replace(/\.textPlot\s*:\s*/gi, '. \\text{Plot: }');

    // 1. Fix common model artifacts like ":;" -> ":"
    clean = clean.replace(/:;/g, ":");

    // 2. Fix double escaped \text if it appears as "\\text" (literal backslash + text)
    clean = clean.replace(/\\\\text/g, "\\text");
    clean = clean.replace(/\\\\quad/g, "\\quad");

    // 3. Fix standalone textLine:, textParabola:, textPlot: at start or after non-letter
    clean = clean.replace(/(^|[^a-zA-Z\\])textLine\s*:\s*/gi, "$1\\text{Line: }");
    clean = clean.replace(/(^|[^a-zA-Z\\])textParabola\s*:\s*/gi, "$1\\text{Parabola: }");
    clean = clean.replace(/(^|[^a-zA-Z\\])textPlot\s*:\s*/gi, "$1\\text{Plot: }");
    clean = clean.replace(/(^|[^a-zA-Z\\])textThus\s*/gi, "$1\\text{Thus }");
    clean = clean.replace(/(^|[^a-zA-Z\\])textWindow\s*/gi, "$1\\text{Window }");
    clean = clean.replace(/(^|[^a-zA-Z\\])textLabel\s*/gi, "$1\\text{Label }");
    clean = clean.replace(/(^|[^a-zA-Z\\])textOther\s*/gi, "$1\\text{Other }");

    // 4. Fix "text{...}" patterns where backslash is missing
    clean = clean.replace(/(^|[^\\])text\{/g, "$1\\text{");

    // 5. GENERAL FIX: Catch ANY "text" followed by a capital letter (CamelCase artifacts)
    // Examples: textOtherpoints, textPlotdomainsuggestion
    clean = clean.replace(/(^|[^a-zA-Z\\])text([A-Z][a-z]+(?:[A-Z][a-z]*)*)/g, (match, prefix, camelText) => {
        // Split CamelCase into words
        const spaced = camelText
            .replace(/([A-Z])/g, ' $1')
            .trim()
            .replace(/\s+/g, ' ');
        return `${prefix}\\text{${spaced} }`;
    });

    // 6. Insert line breaks between Parabola and Line sections for readability
    // Pattern: "). \text{Line" -> "). \\ \text{Line"
    clean = clean.replace(/\)\.\s*(\\text\{Line)/gi, '). \\\\ $1');

    // 7. Improve readability: convert "and" separators to new lines
    clean = clean.replace(/\\quad\\text\{and\}\\quad/g, " \\\\ ");

    // 8. Split comma-separated equations for readability
    clean = clean.replace(/(\w+\s*=[^,]+),\s+(?=\w+\s*=)/g, "$1 \\\\ ");

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
