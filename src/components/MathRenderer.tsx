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

import {
    convertLatexFencesToMath,
    sanitizeLatex,
    normalizeLatexBreaksOutsideMath,
    normalizeAndFixColors,
    escapeAllDollars,
    convertStrictToLibFormat
} from './MathUtils';

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function MathRenderer({ content, className = "", inline = false, forceMath = false }: MathRendererProps) {
    if (content === null || content === undefined) return null;
    let text = String(content);

    // Step 1: Convert fenced ```latex blocks to \[...\] (Strict Block)
    text = convertLatexFencesToMath(text);

    // Step 2: Auto-wrap LaTeX environments (Removed/Disabled)
    // text = autoWrapLatexEnvironments(text);

    // Step 3: Normalize Colors & Fix Prose
    text = normalizeAndFixColors(text);

    // Step 4: Sanitize LaTeX artifacts
    text = sanitizeLatex(text);

    // Step 5: Normalize LaTeX breaks/commands outside math regions
    text = normalizeLatexBreaksOutsideMath(text);

    // Step 6: STRICT: Escape ALL dollars in prose to prevent accidental math mode.
    // This effectively disables $...$ delimiters.
    text = escapeAllDollars(text);

    // Step 7: Force Math Logic (Strict Mode)
    if (forceMath) {
        const trimmed = text.trim();
        // Check for STRICT delimiters only
        const hasDelimiters =
            (trimmed.startsWith('\\(') && trimmed.endsWith('\\)')) ||
            (trimmed.startsWith('\\[') && trimmed.endsWith('\\]'));

        if (!hasDelimiters) {
            // Apply strict delimiters
            const requiresBlock = /\\begin\{|\\\\/.test(text) || !inline;
            if (requiresBlock) {
                text = `\\[${text}\\]`;
            } else {
                text = `\\(${text}\\)`;
            }
        }
    }

    // Step 8: Final Separation: Convert Strict Delimiters to Library Format
    // \( -> $ and \[ -> $$ for remark-math consumption
    text = convertStrictToLibFormat(text);

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
