"use client";

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { segmentMath } from './math/mathSegment';
import {
    sanitizeLatex,
    convertStrictToLibFormat,
} from './MathUtils';

interface MathRendererProps {
    content?: string | number;
    className?: string;
    inline?: boolean;
    forceMath?: boolean;
}

/**
 * MathRenderer (Katex/Remark implementation)
 * 
 * Overhauled to use a robust segmenter that prevents word-gluing
 * and handles naked TeX fragments safely.
 */
export default function MathRenderer({ content, className = "", inline = false, forceMath = false }: MathRendererProps) {
    if (content === null || content === undefined) return null;
    let raw = String(content);

    // Apply strict force math if requested (wrap whole content if no delimiters found)
    if (forceMath && !raw.includes("\\(") && !raw.includes("\\[") && !raw.includes("$")) {
        raw = inline ? `\\(${raw}\\)` : `\\[${raw}\\]`;
    }

    // Segment the content into text and math blocks
    // This is the core fix for "glued words" - text segments are rendered outside of Katex.
    const segments = segmentMath(raw);

    const Wrapper: React.ElementType = inline ? "span" : "div";

    return (
        <Wrapper
            className={`math-renderer markdown-math ${className} ${inline ? "inline-block" : "block"}`}
            style={{ whiteSpace: "pre-wrap" }}
        >
            {segments.map((seg, i) => {
                if (seg.type === "text") {
                    // Render prose as normal span to preserve spaces and font
                    return <span key={`txt-${i}`}>{seg.value}</span>;
                }

                // Construct wrapped TeX for remark-math/rehype-katex
                // seg.value from segmentMath is the naked TeX content
                const wrappedTex = seg.type === "block_math"
                    ? `\\[${seg.value}\\]`
                    : `\\(${seg.value}\\)`;

                // Sanitize and convert for library consumption
                let tex = sanitizeLatex(wrappedTex);
                tex = convertStrictToLibFormat(tex);

                return (
                    <span
                        key={`math-${i}`}
                        className="math-segment-wrap"
                        style={{ display: seg.type === "block_math" ? "block" : "inline-block" }}
                    >
                        <ReactMarkdown
                            remarkPlugins={[remarkMath]}
                            rehypePlugins={[
                                [rehypeKatex, { throwOnError: false, strict: 'ignore' }]
                            ]}
                            components={{
                                // Prevent ReactMarkdown from wrapping every segment in <p>
                                p: ({ children }) => (
                                    <span style={{ display: seg.type === "block_math" ? "block" : "inline" }}>
                                        {children}
                                    </span>
                                ),
                            }}
                        >
                            {tex}
                        </ReactMarkdown>
                    </span>
                );
            })}
        </Wrapper>
    );
}
