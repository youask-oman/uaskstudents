import { assertLatexSafe } from "@/lib/latexSafety";

describe("assertLatexSafe", () => {
  it("returns the same latex when no TAB is present", () => {
    const latex = String.raw`p(3) = -2 \implies \text{Remainder} = -2`;
    expect(assertLatexSafe(latex)).toBe(latex);
  });

  it("throws when latex contains a TAB character", () => {
    const bad = "p(3) = -2 \\implies \t ext{Remainder} = -2";
    expect(() => assertLatexSafe(bad)).toThrow(/TAB character/i);
  });
});

