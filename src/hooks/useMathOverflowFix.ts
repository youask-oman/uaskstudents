/**
 * useMathOverflowFix
 * 
 * React hook that detects math containers that overflow their parent
 * and applies a scale-down transform to fit them.
 * 
 * This is a FALLBACK for pathological cases where MathJax linebreaks
 * and our FinalAnswerLayoutEngine cannot handle extremely long expressions.
 */

import { useEffect, useRef, useCallback } from "react";

export interface MathOverflowFixOptions {
    /** Minimum scale factor (default: 0.7) */
    minScale?: number;
    /** Selector for math containers to check (default: "mjx-container, .MathJax, .katex") */
    selector?: string;
    /** Debounce delay in ms (default: 100) */
    debounceMs?: number;
}

/**
 * Hook to apply scale-down transform to overflowing math elements
 */
export function useMathOverflowFix(
    containerRef: React.RefObject<HTMLElement | null>,
    options: MathOverflowFixOptions = {}
) {
    const {
        minScale = 0.7,
        selector = "mjx-container, .MathJax, .katex",
        debounceMs = 100,
    } = options;

    const timeoutRef = useRef<NodeJS.Timeout | null>(null);

    const checkAndFixOverflow = useCallback(() => {
        const container = containerRef.current;
        if (!container) return;

        const mathElements = container.querySelectorAll<HTMLElement>(selector);

        mathElements.forEach((mathEl) => {
            // Get parent width for comparison
            const parent = mathEl.parentElement;
            if (!parent) return;

            const parentWidth = parent.clientWidth;
            const mathWidth = mathEl.scrollWidth;

            // Reset any previous transforms first
            mathEl.style.transform = "";
            mathEl.style.transformOrigin = "left top";

            // If math overflows, calculate scale to fit
            if (mathWidth > parentWidth && parentWidth > 0) {
                const scale = Math.max(minScale, parentWidth / mathWidth);
                mathEl.style.transform = `scale(${scale})`;
                mathEl.classList.add("mathScaleToFit");

                // Adjust container height to account for scaling
                const originalHeight = mathEl.offsetHeight;
                const scaledHeight = originalHeight * scale;
                mathEl.style.marginBottom = `${scaledHeight - originalHeight}px`;
            } else {
                mathEl.classList.remove("mathScaleToFit");
                mathEl.style.marginBottom = "";
            }
        });
    }, [containerRef, minScale, selector]);

    useEffect(() => {
        // Debounced check function
        const debouncedCheck = () => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
            timeoutRef.current = setTimeout(checkAndFixOverflow, debounceMs);
        };

        // Initial check after MathJax has time to render
        const initialTimeout = setTimeout(checkAndFixOverflow, 500);

        // Use MutationObserver to detect when math content changes
        const container = containerRef.current;
        if (!container) return;

        const observer = new MutationObserver(debouncedCheck);
        observer.observe(container, {
            childList: true,
            subtree: true,
            characterData: true,
        });

        // Also listen for resize
        const resizeObserver = new ResizeObserver(debouncedCheck);
        resizeObserver.observe(container);

        return () => {
            observer.disconnect();
            resizeObserver.disconnect();
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
            clearTimeout(initialTimeout);
        };
    }, [checkAndFixOverflow, debounceMs, containerRef]);

    return { checkAndFixOverflow };
}

/**
 * Standalone function to check if any math elements inside a container overflow
 * Returns true if any overflow is detected.
 */
export function hasMathOverflow(
    container: HTMLElement,
    selector = "mjx-container, .MathJax, .katex"
): boolean {
    const mathElements = container.querySelectorAll<HTMLElement>(selector);

    for (const mathEl of mathElements) {
        if (mathEl.scrollWidth > mathEl.clientWidth || mathEl.scrollHeight > mathEl.clientHeight) {
            return true;
        }
    }

    return false;
}
