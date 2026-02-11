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
    useMathJaxTypeset(wrapperRef, [content, mode, className, dynamic, idKey], 200);
    const Wrapper: React.ElementType = mode === "inline" ? "span" : "div";
    return (
        <Wrapper ref={wrapperRef} className={className}>
            <MathRendererSwitch
                content={content}
                mode={mode}
                dynamic={dynamic}
                idKey={idKey}
            />
        </Wrapper>
    );
}
