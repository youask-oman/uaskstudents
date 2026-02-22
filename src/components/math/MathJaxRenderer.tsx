"use client";

import React from "react";
import MathRendererSwitch from "./MathRendererSwitch";
import MarkdownMathContent from "@/components/math/MarkdownMathContent";

export type MathJaxRenderMode = "prose" | "block" | "inline";

export interface MathJaxRendererProps {
    content: string;
    mode: MathJaxRenderMode;
    className?: string;
    dynamic?: boolean;
    idKey?: string;
    simple?: boolean;
}

export default function MathJaxRenderer({
    content,
    mode,
    className,
    dynamic,
    idKey,
    simple,
}: MathJaxRendererProps) {
    if (mode === "prose") {
        return <MarkdownMathContent content={content} className={className} simple={simple} />;
    }

    if (mode === "inline") {
        return (
            <span className={className}>
                <MathRendererSwitch
                    content={content}
                    mode={mode}
                    dynamic={dynamic}
                    idKey={idKey}
                />
            </span>
        );
    }

    return (
        <span className={className} style={{ display: "block" }}>
            <MathRendererSwitch
                content={content}
                mode={mode}
                dynamic={dynamic}
                idKey={idKey}
            />
        </span>
    );
}
