import { normalizeProseMath } from "../mathNormalize";

describe("normalizeProseMath", () => {
    test("converts fenced latex blocks to display delimiters", () => {
        const input = "Before\n```latex\nx + 1 = 2\n```\nAfter";
        const output = normalizeProseMath(input);
        expect(output).toContain("\\[\nx + 1 = 2\n\\]");
    });

    test("converts $$ blocks to display delimiters", () => {
        const input = "Value:\n$$x^2 + 1$$\nDone";
        const output = normalizeProseMath(input);
        expect(output).toContain("\\[\nx^2 + 1\n\\]");
    });

    test("converts safe inline $...$ pairs", () => {
        const input = "Let $x+1$ be the result.";
        const output = normalizeProseMath(input);
        expect(output).toBe("Let \\(x+1\\) be the result.");
    });

    test("escapes stray dollars and currency", () => {
        const input = "The price is $5 today and $ tomorrow.";
        const output = normalizeProseMath(input);
        expect(output).toContain("\\$5");
        expect(output).toContain("\\$");
    });
});
