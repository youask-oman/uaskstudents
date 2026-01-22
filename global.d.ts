import type { DetailedHTMLProps, HTMLAttributes } from "react";

declare global {
    namespace JSX {
        interface IntrinsicElements {
            "math-field": DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement>;
        }
    }
}
