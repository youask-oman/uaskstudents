"use client";

import React from "react";
import { normalizeProseMath, autoFixMath } from "./mathNormalize";
import { sanitizeLatex } from "../MathUtils";
import { segmentMath } from "./mathSegment";
import {
    markMalformedLatex,
} from "./mathTelemetry";

export type UnifiedMathMode = "prose" | "block" | "inline";

export interface UnifiedMathRendererProps {
    content: string;
    mode: UnifiedMathMode;
    className?: string;
    dynamic?: boolean;
    idKey?: string;
}

const FALLBACK_STYLE: React.CSSProperties = {
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
    fontSize: "0.95em",
    background: "rgba(148, 163, 184, 0.14)",
    padding: "0.1rem 0.25rem",
    borderRadius: "0.25rem",
};

const renderFallback = (value: string) => (
    <span style={FALLBACK_STYLE} className="math-fallback">
        {value}
    </span>
);

export const normalizeInjectedSvg = (svg: string) => {
    if (!svg) return svg;
    // Remove aggressive baseline shifts that can clip standalone SVG in constrained containers.
    return svg
        .replace(/<\?xml[\s\S]*?\?>/gi, "")
        .replace(/\sstyle="([^"]*)"/i, (_m, styleValue: string) => {
            const kept = String(styleValue || "")
                .split(";")
                .map((part) => part.trim())
                .filter((part) => part.length > 0 && !part.toLowerCase().startsWith("vertical-align"))
                .join(";");
            return kept ? ` style="${kept}"` : "";
        })
        .replace(/<rect\b([^>]*)\/?>/gi, (match, attrs: string) => {
            const widthMatch = /\bwidth="([^"]+)"/i.exec(attrs || "");
            const heightMatch = /\bheight="([^"]+)"/i.exec(attrs || "");
            const fillMatch = /\bfill="([^"]+)"/i.exec(attrs || "");
            const classMatch = /\bclass="([^"]+)"/i.exec(attrs || "");
            const styleMatch = /\bstyle="([^"]+)"/i.exec(attrs || "");
            const width = Number.parseFloat((widthMatch?.[1] || "").replace(/[^\d.\-]/g, ""));
            const height = Number.parseFloat((heightMatch?.[1] || "").replace(/[^\d.\-]/g, ""));
            const fill = String(fillMatch?.[1] || "").trim().toLowerCase();
            const style = String(styleMatch?.[1] || "").toLowerCase();
            const className = String(classMatch?.[1] || "").toLowerCase();
            const isHuge = Number.isFinite(width) && Number.isFinite(height) && width >= 1000 && height >= 180;
            const fillIsOpaque = !fill || fill === "currentcolor" || fill === "#000" || fill === "#000000" || fill === "black";
            const styleOpaque =
                style.includes("fill:currentcolor") ||
                style.includes("fill:#000") ||
                style.includes("fill:black");
            const allowByClass = className.includes("graph") || className.includes("plot") || className.includes("axis");
            if (isHuge && !allowByClass && (fillIsOpaque || styleOpaque)) {
                return "";
            }
            return match;
        });
};

interface RenderResult {
    ok: boolean;
    key?: string;
    svg?: string;
}

const buildMathKey = (value: string, inline: boolean) => `${inline ? "i" : "b"}::${value}`;

const normalizeLatexForSvgEngine = (value: string) =>
    String(value || "")
        .replace(/\\left\s*/g, "")
        .replace(/\\right\s*/g, "")
        .trim();

const useMathSvgBatch = (jobs: Array<{ key: string; latex: string; inline: boolean }>, enabled: boolean) => {
    const [renderMap, setRenderMap] = React.useState<Record<string, RenderResult>>({});
    const [loading, setLoading] = React.useState(false);

    React.useEffect(() => {
        if (!enabled || jobs.length === 0) {
            setRenderMap({});
            return;
        }
        const pending = jobs.filter((job) => !renderMap[job.key]);
        if (pending.length === 0) return;

        let cancelled = false;
        const controller = new AbortController();
        const run = async () => {
            setLoading(true);
            try {
                const response = await fetch("/api/v1/math/svg/batch", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        items: pending.map((job) => ({
                            tex: job.latex,
                            display: !job.inline,
                        })),
                    }),
                    signal: controller.signal,
                });
                const payload = await response.json();
                if (cancelled || !Array.isArray(payload?.results)) return;
                setRenderMap((prev) => {
                    const next = { ...prev };
                    for (let i = 0; i < pending.length; i += 1) {
                        const row = payload.results[i];
                        next[pending[i].key] = {
                            ok: Boolean(row?.ok),
                            key: pending[i].key,
                            svg: typeof row?.svg === "string" ? row.svg : undefined,
                        };
                    }
                    return next;
                });
            } catch {
                if (cancelled) return;
                setRenderMap((prev) => {
                    const next = { ...prev };
                    for (const job of pending) next[job.key] = { ok: false };
                    return next;
                });
            } finally {
                if (!cancelled) setLoading(false);
            }
        };
        void run();

        return () => {
            cancelled = true;
            controller.abort();
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [enabled, jobs.map((j) => j.key).join("|")]);

    return { renderMap, loading };
};

const stripOuterDelimiters = (content: unknown) => {
    if (typeof content !== "string") return String(content || "");
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
    result,
}: {
    value: string;
    inline: boolean;
    dynamic?: boolean;
    result?: RenderResult;
}) => {
    if (!value || (typeof value === "string" && !value.trim())) {
        return <span />;
    }

    // Double check if value is still an array/object-like string that needs cleaning before render
    let cleanValue = typeof value === "string" ? sanitizeLatex(autoFixMath(value)) : value;
    if (typeof cleanValue === "string" && cleanValue.trim().startsWith("[") && cleanValue.trim().endsWith("]")) {
        try {
            const parsed = JSON.parse(cleanValue);
            if (Array.isArray(parsed)) cleanValue = parsed.join(" \\quad ");
        } catch {
            // Not valid JSON array, treat as text
        }
    }

    if (isLikelyMalformed(cleanValue)) {
        markMalformedLatex(cleanValue);
        return renderFallback(cleanValue);
    }

    const Wrapper: React.ElementType = "span";
    if (dynamic) {
        return <Wrapper suppressHydrationWarning>{renderFallback(cleanValue)}</Wrapper>;
    }

    if (!result?.ok) {
        return <Wrapper suppressHydrationWarning>{renderFallback(cleanValue)}</Wrapper>;
    }

    if (!result.svg || !result.svg.trim()) {
        return <Wrapper suppressHydrationWarning>{renderFallback(cleanValue)}</Wrapper>;
    }

    const safeSvg = normalizeInjectedSvg(result.svg);
    if (!safeSvg.trim()) {
        return <Wrapper suppressHydrationWarning>{renderFallback(cleanValue)}</Wrapper>;
    }
    return (
        <Wrapper
            suppressHydrationWarning
            role="img"
            aria-label={cleanValue}
            style={{
                display: inline ? "inline-flex" : "block",
                alignItems: inline ? "baseline" : undefined,
                flexWrap: inline ? "nowrap" : undefined,
                verticalAlign: inline ? "baseline" : "middle",
                maxWidth: "100%",
                height: "auto",
                overflow: "visible",
                whiteSpace: inline ? "nowrap" : "normal",
            }}
            dangerouslySetInnerHTML={{ __html: safeSvg }}
        >
            {/* Rendered via sanitized inline SVG */}
        </Wrapper>
    );
};

export default function UnifiedMathRenderer({
    content,
    mode,
    className = "",
    dynamic = false,
    idKey,
}: UnifiedMathRendererProps) {
    const raw = typeof content === "string" ? content : (content ? JSON.stringify(content) : "");
    const [isMounted, setIsMounted] = React.useState(false);

    React.useEffect(() => {
        setIsMounted(true);
    }, []);

    const stripped = React.useMemo(() => stripOuterDelimiters(raw), [raw]);
    const debounced = useDebouncedValue(stripped, dynamic ? 200 : 0);
    const normalized = React.useMemo(() => normalizeProseMath(raw), [raw]);
    const { stable, tail } = useStreamingContent(normalized, dynamic);
    const segments = React.useMemo(() => segmentMath(stable), [stable]);
    const jobs = React.useMemo(() => {
        const collected: Array<{ key: string; latex: string; inline: boolean }> = [];
        const seen = new Set<string>();
        for (const segment of segments) {
            if (segment.type === "text") continue;
            const inline = segment.type === "inline_math";
            const key = buildMathKey(segment.value, inline);
            if (seen.has(key)) continue;
            seen.add(key);
            collected.push({ key, latex: normalizeLatexForSvgEngine(segment.value), inline });
        }
        // For direct inline/block mode, always enqueue exact payload key.
        // This prevents fallback when segmenter captures only a subset of bare LaTeX.
        if (mode === "inline" || mode === "block") {
            const inline = mode === "inline";
            const exactValue = (debounced || stripped || "").trim();
            if (exactValue) {
                const directKey = buildMathKey(exactValue, inline);
                if (!seen.has(directKey)) {
                    seen.add(directKey);
                    collected.push({ key: directKey, latex: normalizeLatexForSvgEngine(exactValue), inline });
                }
            }
        }
        return collected;
    }, [segments, mode, debounced, stripped]);
    const { renderMap, loading } = useMathSvgBatch(jobs, isMounted && !dynamic);
    const keyPrefix = idKey || "math";

    if (!raw) return null;

    if (!isMounted) {
        return (
            <span className={className} style={{ display: mode === "inline" ? "inline" : "block" }} suppressHydrationWarning />
        );
    }

    if (dynamic) {
        const display = mode === "inline" ? "inline" : "block";
        const streamValue = mode === "prose" ? normalized : stripped;
        return (
            <span className={className} style={{ display, whiteSpace: mode === "prose" ? "pre-wrap" : undefined }}>
                {streamValue}
            </span>
        );
    }

    if (mode === "inline" || mode === "block") {
        const value = debounced || stripped;
        const inline = mode === "inline";
        const singleKey = buildMathKey(value, inline);

        return (
            <span className={className} style={{ display: inline ? "inline" : "block" }}>
                <MathSegment value={value} inline={inline} dynamic={dynamic} result={renderMap[singleKey]} />
            </span>
        );
    }

    return (
        <span className={className} style={{ display: "block", whiteSpace: "pre-wrap" }}>
            {segments.map((segment, index) => {
                if (segment.type === "text") {
                    return (
                        <span key={`${keyPrefix}-t-${index}`}>{segment.value}</span>
                    );
                }
                if (segment.type === "inline_math") {
                    const mathKey = buildMathKey(segment.value, true);
                    return (
                        <MathSegment
                            key={`${keyPrefix}-i-${index}`}
                            value={segment.value}
                            inline={true}
                            dynamic={dynamic}
                            result={renderMap[mathKey]}
                        />
                    );
                }
                const mathKey = buildMathKey(segment.value, false);
                return (
                    <MathSegment
                        key={`${keyPrefix}-b-${index}`}
                        value={segment.value}
                        inline={false}
                        dynamic={dynamic}
                        result={renderMap[mathKey]}
                    />
                );
            })}
            {loading ? <span className="math-streaming-tail" /> : null}
            {tail ? <span className="math-streaming-tail">{tail}</span> : null}
        </span>
    );
}
