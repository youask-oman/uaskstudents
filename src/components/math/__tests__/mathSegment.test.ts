import { segmentMath } from "@/components/math/mathSegment";

describe("segmentMath", () => {
  test("does not consume trailing prose when inline delimiter is unmatched", () => {
    const segments = segmentMath("Step text \\(x + 1 and more words");
    expect(segments).toEqual([
      { type: "text", value: "Step text " },
      { type: "text", value: "\\(" },
      { type: "text", value: "x + 1 and more words" },
    ]);
  });
});
