export type StressCase = {
  id: number;
  tex: string;
  display: boolean;
  bracketWrapped: string;
};

function seededRandom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (1664525 * state + 1013904223) >>> 0;
    return state / 0x100000000;
  };
}

function pick<T>(rand: () => number, items: T[]): T {
  return items[Math.floor(rand() * items.length)];
}

const FUNCTIONS = ["\\sin", "\\cos", "\\tan", "\\ln", "\\exp", "\\sqrt"];
const SYMBOLS = ["x", "y", "t", "u", "v", "z"];

function buildCaseTex(rand: () => number, index: number): { tex: string; display: boolean } {
  const x = pick(rand, SYMBOLS);
  const y = pick(rand, SYMBOLS);
  const n = 2 + Math.floor(rand() * 6);
  const a = 1 + Math.floor(rand() * 9);
  const b = 1 + Math.floor(rand() * 9);
  const f = pick(rand, FUNCTIONS);
  const kind = index % 10;

  if (kind === 0) {
    return { tex: `${f}(${x}) + \\frac{${a}${x}^{${n}}}{${b}+${x}} = 0`, display: false };
  }
  if (kind === 1) {
    return {
      tex: `\\int_{0}^{${n}} \\left(${a}${x}^2 - ${b}${x} + 1\\right)\\,d${x} = ${a}\\frac{${n}^3}{3} - ${b}\\frac{${n}^2}{2} + ${n}`,
      display: true,
    };
  }
  if (kind === 2) {
    return { tex: `\\sum_{k=1}^{${n * 2}} \\frac{1}{k^2} \\approx \\frac{\\pi^2}{6}`, display: true };
  }
  if (kind === 3) {
    return { tex: `\\lim_{${x}\\to 0} \\frac{\\sin(${a}${x})}{${x}} = ${a}`, display: false };
  }
  if (kind === 4) {
    return {
      tex: `\\begin{aligned}${a}${x} + ${b}${y} &= ${a + b} \\\\ ${b}${x} - ${a}${y} &= ${b - a}\\end{aligned}`,
      display: true,
    };
  }
  if (kind === 5) {
    return {
      tex: `\\begin{bmatrix}${a} & ${b} \\\\ ${b + 1} & ${a + 2}\\end{bmatrix} \\cdot \\begin{bmatrix}${x} \\\\ ${y}\\end{bmatrix}`,
      display: true,
    };
  }
  if (kind === 6) {
    return { tex: `${x}'(t) + ${a}${x}(t) = ${b}e^{-t}`, display: false };
  }
  if (kind === 7) {
    return { tex: `\\frac{d^2${x}}{d${y}^2} + ${a}\\frac{d${x}}{d${y}} + ${b}${x} = 0`, display: false };
  }
  if (kind === 8) {
    return { tex: `${a}(${x}^2 - ${b}${x} + ${n})=0 \\implies ${x}=\\frac{${b}\\pm\\sqrt{${b * b}-${4 * n}}}{2}`, display: true };
  }
  return {
    tex: `f(${x})=\\begin{cases}${a}${x}^2-${b} & ${x}\\ge 0 \\\\ -${a}${x}+${b} & ${x}<0\\end{cases}`,
    display: true,
  };
}

export function generateStressCases(count = 1000, seed = 20260222): StressCase[] {
  const rand = seededRandom(seed);
  const out: StressCase[] = [];
  for (let i = 0; i < count; i += 1) {
    const { tex, display } = buildCaseTex(rand, i);
    out.push({
      id: i + 1,
      tex,
      display,
      bracketWrapped: `[ ${tex} ]`,
    });
  }
  return out;
}

