import { segmentMath } from "../mathSegment";

describe("segmentMath", () => {
    test("segments inline and block math while preserving text", () => {
        const input = "Let \\(x=2\\) then \\[x^2=4\\].";
        const segments = segmentMath(input);
        expect(segments).toEqual([
            { type: "text", value: "Let " },
            { type: "inline_math", value: "x=2" },
            { type: "text", value: " then " },
            { type: "block_math", value: "x^2=4" },
            { type: "text", value: "." },
        ]);
    });

    test("leaves unmatched delimiters as text", () => {
        const input = "Unclosed \\(x+1";
        const segments = segmentMath(input);
        expect(segments).toEqual([
            { type: "text", value: "Unclosed " },
            { type: "text", value: "\\(x+1" },
        ]);
    });
});
