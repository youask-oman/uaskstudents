import { normalizeInjectedSvg } from "@/components/math/UnifiedMathRenderer";

describe("normalizeInjectedSvg", () => {
  test("removes oversized opaque rect overlays from math svg", () => {
    const input = '<svg viewBox="0 0 200 50"><rect width="13800" height="950" y="-200"></rect><g><text>x</text></g></svg>';
    const out = normalizeInjectedSvg(input);
    expect(out).not.toContain('width="13800"');
    expect(out).toContain("<text>x</text>");
  });

  test("keeps normal graph-like rects", () => {
    const input = '<svg><rect class="graph-axis-bg" width="200" height="120" fill="#fff"></rect></svg>';
    const out = normalizeInjectedSvg(input);
    expect(out).toContain('class="graph-axis-bg"');
    expect(out).toContain('width="200"');
  });
});

