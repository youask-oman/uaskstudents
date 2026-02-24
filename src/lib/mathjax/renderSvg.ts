import { LRUCache } from "lru-cache";
import { mathjax } from "mathjax-full/js/mathjax.js";
import { TeX } from "mathjax-full/js/input/tex.js";
import { SVG } from "mathjax-full/js/output/svg.js";
import { liteAdaptor } from "mathjax-full/js/adaptors/liteAdaptor.js";
import { RegisterHTMLHandler } from "mathjax-full/js/handlers/html.js";
import { AllPackages } from "mathjax-full/js/input/tex/AllPackages.js";

type RenderOptions = {
  display: boolean;
};

export type RenderSvgResult =
  | { ok: true; svg: string }
  | { ok: false; error: string };

const cache = new LRUCache<string, RenderSvgResult>({
  max: 5000,
  ttl: 1000 * 60 * 60 * 24,
});

let initialized = false;
let adaptor: ReturnType<typeof liteAdaptor>;
let texInput: TeX<unknown, unknown, unknown>;
let svgOutput: SVG<unknown, unknown, unknown>;
let htmlDocument: ReturnType<typeof mathjax.document>;

function initMathJaxOnce(): void {
  if (initialized) return;

  adaptor = liteAdaptor();
  RegisterHTMLHandler(adaptor);

  texInput = new TeX({
    packages: AllPackages,
  });

  svgOutput = new SVG({
    fontCache: "local",
  });

  htmlDocument = mathjax.document("", {
    InputJax: texInput,
    OutputJax: svgOutput,
  });

  initialized = true;
}

function cacheKey(tex: string, display: boolean): string {
  return `${display ? "D" : "I"}::${tex.trim()}`;
}

export function renderTexToSvg(tex: string, options: RenderOptions): RenderSvgResult {
  initMathJaxOnce();

  const key = cacheKey(tex, options.display);
  const hit = cache.get(key);
  if (hit) return hit;

  try {
    const node = htmlDocument.convert(tex, { display: options.display });
    const svg = adaptor.outerHTML(node);

    if (/<script\b/i.test(svg)) {
      const unsafe: RenderSvgResult = { ok: false, error: "Unsafe SVG output." };
      cache.set(key, unsafe);
      return unsafe;
    }

    const result: RenderSvgResult = { ok: true, svg };
    cache.set(key, result);
    return result;
  } catch (error) {
    const message = error instanceof Error ? error.message : "MathJax render failed.";
    const result: RenderSvgResult = { ok: false, error: message };
    cache.set(key, result);
    return result;
  }
}
