"use client";

import React from "react";
import MathRendererSwitch from "./MathRendererSwitch";

export type MathJaxRenderMode = "prose" | "block" | "inline";

export interface MathJaxRendererProps {
    content: string;
    mode: MathJaxRenderMode;
    className?: string;
    dynamic?: boolean;
    idKey?: string;
}

export default function MathJaxRenderer({
    content,
    mode,
    className,
    dynamic,
    idKey,
}: MathJaxRendererProps) {
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
        <div className={className}>
            <MathRendererSwitch
                content={content}
                mode={mode}
                dynamic={dynamic}
                idKey={idKey}
            />
        </div>
    );
}
