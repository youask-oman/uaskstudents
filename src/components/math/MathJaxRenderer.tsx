"use client";

import React from "react";
import MathRendererSwitch from "./MathRendererSwitch";
import { useMathJaxTypeset } from "./useMathJaxTypeset";

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
    const wrapperRef = React.useRef<HTMLSpanElement | HTMLDivElement>(null);
    useMathJaxTypeset(wrapperRef as React.RefObject<HTMLElement>, [content, mode, className, dynamic, idKey], 200);
    if (mode === "inline") {
        return (
            <span ref={wrapperRef as React.Ref<HTMLSpanElement>} className={className}>
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
        <div ref={wrapperRef as React.Ref<HTMLDivElement>} className={className}>
            <MathRendererSwitch
                content={content}
                mode={mode}
                dynamic={dynamic}
                idKey={idKey}
            />
        </div>
    );
}
