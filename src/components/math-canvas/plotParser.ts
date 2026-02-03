import { PlotDataPoint } from "./types";

const parseCoefficient = (raw: string | undefined, fallback: number): number => {
  if (!raw || raw.trim() === "") return fallback;
  if (raw === "+") return 1;
  if (raw === "-") return -1;
  const value = Number(raw);
  return Number.isFinite(value) ? value : fallback;
};

const sampleRange = (min = -10, max = 10, step = 1): number[] => {
  const out: number[] = [];
  for (let current = min; current <= max; current += step) {
    out.push(Number(current.toFixed(4)));
  }
  return out;
};

const buildFromFunction = (expression: string): PlotDataPoint[] => {
  const normalized = expression.replace(/\s+/g, "").toLowerCase().replace(/^y=/, "");
  if (!normalized) throw new Error("Function is empty.");

  if (normalized === "x") {
    return sampleRange().map((x) => ({ x, y: x }));
  }

  if (normalized === "sin(x)") {
    return sampleRange(-10, 10, 0.5).map((x) => ({ x, y: Number(Math.sin(x).toFixed(6)) }));
  }
  if (normalized === "cos(x)") {
    return sampleRange(-10, 10, 0.5).map((x) => ({ x, y: Number(Math.cos(x).toFixed(6)) }));
  }
  if (normalized === "tan(x)") {
    return sampleRange(-4, 4, 0.2).map((x) => ({ x, y: Number(Math.tan(x).toFixed(6)) }));
  }

  const quadratic = normalized.match(/^([+\-]?\d*\.?\d*)x\^2([+\-]\d*\.?\d*x)?([+\-]\d*\.?\d+)?$/);
  if (quadratic) {
    const a = parseCoefficient(quadratic[1], 1);
    const bPart = quadratic[2]?.replace("x", "");
    const b = bPart ? parseCoefficient(bPart, 0) : 0;
    const c = quadratic[3] ? parseCoefficient(quadratic[3], 0) : 0;
    return sampleRange().map((x) => ({ x, y: Number((a * x * x + b * x + c).toFixed(6)) }));
  }

  const linear = normalized.match(/^([+\-]?\d*\.?\d*)x([+\-]\d*\.?\d+)?$/);
  if (linear) {
    const a = parseCoefficient(linear[1], 1);
    const b = linear[2] ? parseCoefficient(linear[2], 0) : 0;
    return sampleRange().map((x) => ({ x, y: Number((a * x + b).toFixed(6)) }));
  }

  const constant = Number(normalized);
  if (Number.isFinite(constant)) {
    return sampleRange().map((x) => ({ x, y: constant }));
  }

  throw new Error("Unsupported function format. Try y = x, y = 2x+1, y = x^2+3x+2, y = sin(x).");
};

const buildFromPoints = (input: string): PlotDataPoint[] => {
  const rows = input
    .split(/\r?\n/)
    .map((row) => row.trim())
    .filter(Boolean);

  const points: PlotDataPoint[] = [];
  rows.forEach((row) => {
    const cleaned = row.replace(/[()]/g, "");
    const parts = cleaned.split(/[,\s]+/).filter(Boolean);
    if (parts.length < 2) throw new Error(`Invalid point row: "${row}"`);
    const x = Number(parts[0]);
    const y = Number(parts[1]);
    if (!Number.isFinite(x) || !Number.isFinite(y)) throw new Error(`Invalid numbers in row: "${row}"`);
    points.push({ x, y });
  });

  if (points.length < 2) throw new Error("At least 2 points are required.");
  return points;
};

export interface PlotInput {
  mode: "function" | "points";
  expression?: string;
  pointsText?: string;
}

export const parsePlotInput = (input: PlotInput): PlotDataPoint[] => {
  if (input.mode === "function") {
    const expression = (input.expression || "").trim();
    if (!expression) throw new Error("Enter a function expression.");
    return buildFromFunction(expression);
  }
  const pointsText = (input.pointsText || "").trim();
  if (!pointsText) throw new Error("Enter points to plot.");
  return buildFromPoints(pointsText);
};
