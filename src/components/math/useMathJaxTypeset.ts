"use client";

import { useEffect, useRef } from "react";

type MathJaxGlobal = {
    typesetPromise?: (elements?: Element[]) => Promise<void>;
};

const getMathJax = (): MathJaxGlobal | null => {
    if (typeof window === "undefined") return null;
    return (window as unknown as { MathJax?: MathJaxGlobal }).MathJax || null;
};

export const useMathJaxTypeset = (
    containerRef: React.RefObject<HTMLElement | null>,
    deps: unknown[],
    throttleMs = 200
) => {
    const timerRef = useRef<number | null>(null);

    useEffect(() => {
        const mathJax = getMathJax();
        if (!mathJax?.typesetPromise || !containerRef.current) return;

        if (timerRef.current) {
            window.clearTimeout(timerRef.current);
        }
        timerRef.current = window.setTimeout(() => {
            const element = containerRef.current;
            if (element) {
                void mathJax.typesetPromise?.([element]);
            }
        }, throttleMs);

        return () => {
            if (timerRef.current) {
                window.clearTimeout(timerRef.current);
            }
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, deps);
};
