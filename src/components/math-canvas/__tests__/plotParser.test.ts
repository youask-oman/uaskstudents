import { parsePlotInput } from "@/components/math-canvas/plotParser";

describe("plotParser", () => {
  test("parses supported function format", () => {
    const points = parsePlotInput({ mode: "function", expression: "y = x^2 + 2x + 1" });
    expect(points.length).toBeGreaterThan(5);
    const zero = points.find((point) => point.x === 0);
    expect(zero?.y).toBe(1);
  });

  test("parses point rows", () => {
    const points = parsePlotInput({ mode: "points", pointsText: "(0,0)\n(2,4)\n(3,9)" });
    expect(points).toEqual([
      { x: 0, y: 0 },
      { x: 2, y: 4 },
      { x: 3, y: 9 },
    ]);
  });

  test("throws for invalid point payload", () => {
    expect(() => parsePlotInput({ mode: "points", pointsText: "(0,a)" })).toThrow("Invalid numbers");
  });
});
