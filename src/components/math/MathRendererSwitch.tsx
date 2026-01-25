"use client";

import React from "react";
import dynamicLoader from "next/dynamic";
import UnifiedMathRenderer, { UnifiedMathMode } from "./UnifiedMathRenderer";
import { setRenderEngineUsed } from "./mathTelemetry";

export interface MathRendererSwitchProps {
    content: string;
    mode: UnifiedMathMode;
    className?: string;
    dynamic?: boolean;
    idKey?: string;
}

const mathEngine =
    process.env.NEXT_PUBLIC_MATH_ENGINE ||
    process.env.NEXT_PUBLIC_MATH_RENDERER ||
    "mathjax";

export default function MathRendererSwitch({
    content,
    mode,
    className = "",
    dynamic = false,
    idKey,
}: MathRendererSwitchProps) {
    const engine = mathEngine === "katex" ? "katex" : "mathjax";
    const [isMounted, setIsMounted] = React.useState(false);

    React.useEffect(() => {
        setRenderEngineUsed(engine);
    }, [engine]);

    React.useEffect(() => {
        setIsMounted(true);
    }, []);

    if (!isMounted && engine === "mathjax") {
        return <span className={className} suppressHydrationWarning />;
    }

    if (engine === "katex") {
        const LegacyMathRenderer = dynamicLoader(
            () => import("../MathRenderer").then((mod) => mod.default),
            { ssr: false }
        );
        const inline = mode === "inline";
        const forceMath = mode !== "prose";
        return (
            <LegacyMathRenderer
                content={content}
                inline={inline}
                forceMath={forceMath}
                className={className}
            />
        );
    }

    return (
        <UnifiedMathRenderer
            content={content}
            mode={mode}
            className={className}
            dynamic={dynamic}
            idKey={idKey}
        />
    );
}
