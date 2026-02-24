/** @jest-environment node */

import remarkLatexDelimiters from "@/lib/remark/remarkLatexDelimiters";

type TestNode = {
  type?: string;
  value?: unknown;
  children?: TestNode[];
};

function applyToText(input: string): TestNode[] {
  const tree: TestNode = {
    type: "root",
    children: [
      {
        type: "paragraph",
        children: [{ type: "text", value: input }],
      },
    ],
  };
  const transform = remarkLatexDelimiters();
  transform(tree);
  return tree.children?.[0]?.children || [];
}

describe("remarkLatexDelimiters", () => {
  it("converts bracket math from real bad output", () => {
    const input = "First: [ f'(x)=3x^2-12x+9 ] and [ 3(x^2-4x+3)=0 \\implies 3(x-1)(x-3)=0 ]";
    const children = applyToText(input);
    const mathValues = children.filter((n) => n.type === "inlineMath" || n.type === "math").map((n) => String(n.value || ""));
    expect(mathValues).toContain("f'(x)=3x^2-12x+9");
    expect(mathValues).toContain("3(x^2-4x+3)=0 \\implies 3(x-1)(x-3)=0");
  });

  it("converts parenthesized math-like fragments from model prose", () => {
    const input = "The second derivative of ( f(x) ) is: [ f''(x)=6x-12 ]";
    const children = applyToText(input);
    const mathValues = children.filter((n) => n.type === "inlineMath" || n.type === "math").map((n) => String(n.value || ""));
    expect(mathValues).toContain("f(x)");
    expect(mathValues).toContain("f''(x)=6x-12");
  });

  it("does not mangle task list and citation brackets", () => {
    const input = "- [x] task list item\n\nReference [1]";
    const children = applyToText(input);
    const textCombined = children.map((n) => String(n.value || "")).join("");
    expect(textCombined).toContain("- [x] task list item");
    expect(textCombined).toContain("Reference [1]");
    expect(children.some((n) => n.type === "inlineMath" || n.type === "math")).toBe(false);
  });

  it("handles screenshot-style mixed prose with bracket math", () => {
    const input =
      "The second derivative of ( f(x) ) is: [ f''(x)=6x-12 ] Evaluating: [ f'(1)=6(1)-12=-6<0 ] and [ x \\approx 2.556 ]";
    const children = applyToText(input);
    const mathValues = children.filter((n) => n.type === "inlineMath" || n.type === "math").map((n) => String(n.value || ""));
    expect(mathValues).toEqual(
      expect.arrayContaining(["f(x)", "f''(x)=6x-12", "f'(1)=6(1)-12=-6<0", "x \\approx 2.556"])
    );
  });
});
