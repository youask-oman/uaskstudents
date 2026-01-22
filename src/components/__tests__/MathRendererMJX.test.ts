import { prepareMathJaxContent } from "../MathRendererMJX";

describe("MathRendererMJX helper", () => {
  test("converts inline dollar math while preserving spacing", () => {
    const input = "Check substitution $x + 1 = 2$ and keep the prose spacing.";
    const expected = "Check substitution \\(x + 1 = 2\\) and keep the prose spacing.";
    expect(prepareMathJaxContent(input)).toBe(expected);
  });

  test("escapes stray dollars in long prose", () => {
    const input =
      "Total cost is $5; there is no math here, just a stray dollar followed by today $.";
    const output = prepareMathJaxContent(input);
    expect(output).toContain("\\$5");
    expect(output).toContain("\\$.");
  });

  test("wraps bare latex fragments without delimiters", () => {
    const input = "Given f(x)=\\frac{x^2+1}{x-1} and x \\neq 1.";
    const output = prepareMathJaxContent(input);
    expect(output).toContain("\\(\\frac{x^2+1}{x-1}\\)");
    expect(output).toContain("\\(\\neq 1\\)");
  });

  test("outputs a representative step explanation without mangling spaces", () => {
    const stepExplanation = `
Step 2: Square both sides and simplify.

We start with $x + 3 = 7$ and square to get:
$$
x^2 + 6x + 9 = 49
$$
Now we collect like terms and solve for $x$.
`;
    expect(prepareMathJaxContent(stepExplanation)).toMatchSnapshot();
  });
});
