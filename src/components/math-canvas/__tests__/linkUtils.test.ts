import { normalizeLinkInput, validateAndNormalizeLink } from "@/components/math-canvas/rich-text/linkUtils";

describe("rich text link utils", () => {
  test("normalizes missing scheme to https", () => {
    expect(normalizeLinkInput("example.com/path")).toBe("https://example.com/path");
  });

  test("normalizes plain email to mailto", () => {
    expect(normalizeLinkInput("student@uask.ai")).toBe("mailto:student@uask.ai");
  });

  test("rejects unsafe protocols", () => {
    const parsed = validateAndNormalizeLink("javascript:alert(1)");
    expect(parsed.ok).toBe(false);
  });

  test("accepts valid https urls", () => {
    const parsed = validateAndNormalizeLink("https://uask.ai/learn");
    expect(parsed.ok).toBe(true);
    expect(parsed.normalized).toMatch(/^https:\/\/uask\.ai/);
  });
});

