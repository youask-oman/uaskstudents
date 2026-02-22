/** @jest-environment node */

import { renderTexToSvg } from "@/lib/mathjax/renderSvg";
import { generateStressCases } from "@/lib/mathjax/stressCases";

describe("renderTexToSvg stress", () => {
  it("renders 1000 complex equations/functions to SVG without failures", () => {
    const cases = generateStressCases(1000, 20260222);
    const failed: Array<{ id: number; error: string }> = [];

    for (const item of cases) {
      const result = renderTexToSvg(item.tex, { display: item.display });
      if (!result.ok || !result.svg.includes("<svg")) {
        failed.push({ id: item.id, error: result.ok ? "missing_svg" : result.error });
      }
    }

    expect(failed).toHaveLength(0);
  });
});

