"use client";

import React from "react";
import { MathJax } from "better-react-mathjax";
import { normalizeProseMath } from "./mathNormalize";
import { segmentMath } from "./mathSegment";
import {
    markMalformedLatex,
    markTypesetFailure,
    recordTypesetDuration,
} from "./mathTelemetry";

export type UnifiedMathMode = "prose" | "block" | "inline";

export interface UnifiedMathRendererProps {
    content: string;
    mode: UnifiedMathMode;
    className?: string;
    dynamic?: boolean;
    idKey?: string;
}

class MathErrorBoundary extends React.Component<
    { fallback: React.ReactNode; onError: (error: unknown) => void; children: React.ReactNode },
    { hasError: boolean }
> {
    state = { hasError: false };

    static getDerivedStateFromError() {
        return { hasError: true };
    }

    componentDidCatch(error: unknown) {
        this.props.onError(error);
    }

    render() {
        if (this.state.hasError) return this.props.fallback;
        return this.props.children;
    }
}

const FALLBACK_STYLE: React.CSSProperties = {
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
    fontSize: "0.95em",
    background: "rgba(15, 23, 42, 0.08)",
    padding: "0.1rem 0.25rem",
    borderRadius: "0.25rem",
};

const renderFallback = (value: string) => (
    <span style={FALLBACK_STYLE} className="math-fallback">
        {value}
    </span>
);

const stripOuterDelimiters = (content: string) => {
    const trimmed = content.trim();
    if ((trimmed.startsWith("\\(") && trimmed.endsWith("\\)")) ||
        (trimmed.startsWith("\\[") && trimmed.endsWith("\\]"))) {
        return trimmed.slice(2, -2).trim();
    }
    if ((trimmed.startsWith("$$") && trimmed.endsWith("$$")) ||
        (trimmed.startsWith("$") && trimmed.endsWith("$"))) {
        return trimmed.slice(trimmed.startsWith("$$") ? 2 : 1, trimmed.endsWith("$$") ? -2 : -1).trim();
    }
    return content;
};

const hasUnbalancedBraces = (value: string) => {
    let depth = 0;
    for (let i = 0; i < value.length; i += 1) {
        const ch = value[i];
        if (ch === "{" && !isEscaped(value, i)) depth += 1;
        if (ch === "}" && !isEscaped(value, i)) depth -= 1;
        if (depth < 0) return true;
    }
    return depth !== 0;
};

const hasUnbalancedEnvironments = (value: string) => {
    const begins = value.match(/\\begin\{[^}]+\}/g) || [];
    const ends = value.match(/\\end\{[^}]+\}/g) || [];
    return begins.length !== ends.length;
};

const isLikelyMalformed = (value: string) => {
    return hasUnbalancedBraces(value) || hasUnbalancedEnvironments(value);
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

const findStreamingBoundary = (text: string) => {
    const doubleNewline = text.lastIndexOf("\n\n");
    let lastSentence = -1;
    const regex = /[.!?](\s+|$)/g;
    let match: RegExpExecArray | null;
    while ((match = regex.exec(text)) !== null) {
        lastSentence = match.index + 1;
    }
    return Math.max(doubleNewline === -1 ? -1 : doubleNewline + 2, lastSentence);
};

const useDebouncedValue = (value: string, delayMs: number) => {
    const [debounced, setDebounced] = React.useState(value);

    React.useEffect(() => {
        const timer = setTimeout(() => setDebounced(value), delayMs);
        return () => clearTimeout(timer);
    }, [value, delayMs]);

    return debounced;
};

const useStreamingContent = (value: string, dynamic?: boolean) => {
    const [stable, setStable] = React.useState(value);
    const [tail, setTail] = React.useState("");

    React.useEffect(() => {
        if (!dynamic) {
            setStable(value);
            setTail("");
            return;
        }

        const boundary = findStreamingBoundary(value);
        if (boundary > 0) {
            setTail(value.slice(boundary));
            const timer = setTimeout(() => setStable(value.slice(0, boundary)), 200);
            return () => clearTimeout(timer);
        }

        setTail(value);
        const timer = setTimeout(() => setStable(""), 200);
        return () => clearTimeout(timer);
    }, [value, dynamic]);

    return { stable, tail };
};

const MathSegment = ({
    value,
    inline,
    dynamic,
}: {
    value: string;
    inline: boolean;
    dynamic?: boolean;
}) => {
    if (isLikelyMalformed(value)) {
        markMalformedLatex(value);
        return renderFallback(value);
    }

    const startRef = React.useRef<number | null>(null);
    const wrapped = inline ? `\\(${value}\\)` : `\\[${value}\\]`;

    return (
        <MathErrorBoundary fallback={renderFallback(value)} onError={markTypesetFailure}>
            <MathJax
                inline={inline}
                dynamic={dynamic}
                hideUntilTypeset="first"
                renderMode="post"
                onInitTypeset={() => {
                    startRef.current = performance.now();
                }}
                onTypeset={() => {
                    if (startRef.current !== null) {
                        recordTypesetDuration(performance.now() - startRef.current);
                        startRef.current = null;
                    }
                }}
            >
                {wrapped}
            </MathJax>
        </MathErrorBoundary>
    );
};

export default function UnifiedMathRenderer({
    content,
    mode,
    className = "",
    dynamic = false,
    idKey,
}: UnifiedMathRendererProps) {
    const raw = content ?? "";

    const stripped = React.useMemo(() => stripOuterDelimiters(raw), [raw]);
    const debounced = useDebouncedValue(stripped, dynamic ? 200 : 0);
    const normalized = React.useMemo(() => normalizeProseMath(raw), [raw]);
    const { stable, tail } = useStreamingContent(normalized, dynamic);
    const segments = React.useMemo(() => segmentMath(stable), [stable]);
    const keyPrefix = idKey || "math";

    if (!raw) return null;

    if (mode === "inline" || mode === "block") {
        const value = dynamic ? debounced : stripped;
        const inline = mode === "inline";
        const Wrapper: React.ElementType = inline ? "span" : "div";

        return (
            <Wrapper className={className}>
                <MathSegment value={value} inline={inline} dynamic={dynamic} />
            </Wrapper>
        );
    }

    return (
        <div className={className} style={{ whiteSpace: "pre-wrap" }}>
            {segments.map((segment, index) => {
                if (segment.type === "text") {
                    return (
                        <span key={`${keyPrefix}-t-${index}`}>{segment.value}</span>
                    );
                }
                if (segment.type === "inline_math") {
                    return (
                        <MathSegment
                            key={`${keyPrefix}-i-${index}`}
                            value={segment.value}
                            inline={true}
                            dynamic={dynamic}
                        />
                    );
                }
                return (
                    <MathSegment
                        key={`${keyPrefix}-b-${index}`}
                        value={segment.value}
                        inline={false}
                        dynamic={dynamic}
                    />
                );
            })}
            {tail ? <span className="math-streaming-tail">{tail}</span> : null}
        </div>
    );
}
