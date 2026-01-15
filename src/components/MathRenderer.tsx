
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

// Helper to clean and normalize LaTeX from the model
function sanitizeLatex(input: string): string {
    let clean = input;

    // 1. Fix common model artifacts like ":;" -> ":"
    clean = clean.replace(/:;/g, ":");

    // 2. Fix double escaped \text if it appears as "\\text" (literal backslash + text)
    // This happens if the model output escapes the backslash for JSON string.
    clean = clean.replace(/\\\\text/g, "\\text");
    clean = clean.replace(/\\\\quad/g, "\\quad");

    // 3. Improve readability: convert specific "and" separators to new lines
    // Pattern: \quad\text{and}\quad -> \\ (newline)
    clean = clean.replace(/\\quad\\text\{and\}\\quad/g, " \\\\ ");

    // 4. Split comma-separated equations like "x = 3, y = 9" into new lines
    // Look for "Something = Something, Something =" pattern
    clean = clean.replace(/(\w+\s*=[^,]+),\s+(?=\w+\s*=)/g, "$1 \\\\ ");

    // 5. CRITICAL FIX: Repair "text{...}" patterns where backslash is missing.
    // This fixes "connected words" issues because KaTeX eats spaces in "text{...}" but preserves them in "\text{...}"
    // We look for "text{" preceded by start-of-line or non-backslash char.
    clean = clean.replace(/(^|[^\\])text\{/g, "$1\\text{");

    // 6. GENERAL FIX: Catch ANY "text" followed by a capital letter (CamelCase artifacts)
    // Examples: textOtherpoints, textLine, textThus, textPlotdomainsuggestion
    // This regex finds "text" followed by uppercase, captures the rest, and converts to "\text{...}"
    // We also insert spaces between CamelCase words for readability.
    clean = clean.replace(/(^|[^\\])text([A-Z][a-z]+(?:[A-Z][a-z]*)*)/g, (match, prefix, camelText) => {
        // Split CamelCase into words: "Otherpoints" -> "Other points", "Plotdomainsuggestion" -> "Plot domain suggestion"
        const spaced = camelText
            .replace(/([A-Z])/g, ' $1')  // Add space before each capital
            .trim()                        // Remove leading space
            .replace(/\s+/g, ' ');         // Normalize multiple spaces
        return `${prefix}\\text{${spaced} }`;
    });

    // Also catch patterns like "textOther points :" where there's already some spacing
    clean = clean.replace(/(^|[^\\])text([A-Z][a-z]+)\s*:/g, "$1\\text{$2: }");

    return clean;
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
