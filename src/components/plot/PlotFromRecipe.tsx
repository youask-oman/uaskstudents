"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

type Recipe = Record<string, unknown>;

const num = (v: unknown, fallback: number) => (Number.isFinite(Number(v)) ? Number(v) : fallback);

const normalizeExpr = (expr: string): string => {
  let source = String(expr || "").trim();
  if (!source) return source;

  source = source
    .replace(/\\left|\\right/g, "")
    .replace(/\\cdot/g, "*")
    .replace(/\\pi/g, "pi")
    .replace(/\\sin/g, "sin")
    .replace(/\\cos/g, "cos")
    .replace(/\\tan/g, "tan")
    .replace(/\\sqrt/g, "sqrt")
    .replace(/\\log/g, "log")
    .replace(/\\exp/g, "exp")
    .replace(/\^/g, "**");

  // function forms like "cos t" -> "cos(t)"
  source = source.replace(/\b(sin|cos|tan|sqrt|log|exp|abs)\s+([A-Za-z][A-Za-z0-9_]*)/g, "$1($2)");

  // implicit multiplication: 2x, 5cos(t), x(y+1), )x
  source = source
    .replace(/(\d)([A-Za-z(])/g, "$1*$2")
    .replace(/([A-Za-z)])(\d)/g, "$1*$2")
    .replace(/([A-Za-z)])\(/g, "$1*(");

  // remove leading y=... for function series formulas
  source = source.replace(/^\s*y\s*=\s*/i, "");
  return source;
};

const evalExpr = (expr: string, vars: Record<string, number>): number => {
  const source = normalizeExpr(expr);
  const fn = new Function(
    ...Object.keys(vars),
    "sin",
    "cos",
    "tan",
    "sqrt",
    "log",
    "exp",
    "abs",
    "pi",
    `return (${source});`
  );
  return Number(
    fn(
      ...Object.values(vars),
      Math.sin,
      Math.cos,
      Math.tan,
      Math.sqrt,
      Math.log,
      Math.exp,
      Math.abs,
      Math.PI
    )
  );
};

export default function PlotFromRecipe({ recipe }: { recipe: Recipe }) {
  const traces = useMemo(() => {
    const out: Array<Record<string, unknown>> = [];
    const series = Array.isArray(recipe?.series) ? recipe.series : [];
    for (const raw of series) {
      if (!raw || typeof raw !== "object") continue;
      const s = raw as Record<string, unknown>;
      const label = String(s.label || s.series_id || "series");
      const samples = Array.isArray(s.samples) ? s.samples : [];
      if (samples.length > 0) {
        const xs = samples.map((p) => num((p as Record<string, unknown>).x, 0));
        const ys = samples.map((p) => num((p as Record<string, unknown>).y, 0));
        out.push({ type: "scatter", mode: "lines", name: label, x: xs, y: ys });
        continue;
      }

      const kind = String(s.kind || "").toLowerCase();
      const xMin = num((recipe?.x_domain as Record<string, unknown>)?.min, -10);
      const xMax = num((recipe?.x_domain as Record<string, unknown>)?.max, 10);
      const n = 400;
      if (kind === "function" && (typeof s.y_expr_latex === "string" || typeof s.expr_latex === "string")) {
        const fnExpr = typeof s.y_expr_latex === "string" ? String(s.y_expr_latex) : String(s.expr_latex || "");
        const xs: number[] = [];
        const ys: number[] = [];
        for (let i = 0; i < n; i += 1) {
          const x = xMin + ((xMax - xMin) * i) / (n - 1);
          let y = NaN;
          try {
            y = evalExpr(fnExpr, { x });
          } catch {
            y = NaN;
          }
          if (Number.isFinite(y)) {
            xs.push(x);
            ys.push(y);
          }
        }
        out.push({ type: "scatter", mode: "lines", name: label, x: xs, y: ys });
      }
      if (kind === "parametric" && typeof s.x_expr_latex === "string" && typeof s.y_expr_latex === "string") {
        const ts: number[] = [];
        const xs: number[] = [];
        const ys: number[] = [];
        for (let i = 0; i < n; i += 1) {
          const t = ((Math.PI * 2) * i) / (n - 1);
          let x = NaN;
          let y = NaN;
          try {
            x = evalExpr(String(s.x_expr_latex), { t });
            y = evalExpr(String(s.y_expr_latex), { t });
          } catch {
            // no-op
          }
          if (Number.isFinite(x) && Number.isFinite(y)) {
            ts.push(t);
            xs.push(x);
            ys.push(y);
          }
        }
        out.push({ type: "scatter", mode: "lines", name: label, x: xs, y: ys });
      }
    }
    const points = Array.isArray(recipe?.points) ? recipe.points : [];
    if (points.length > 0) {
      out.push({
        type: "scatter",
        mode: "markers+text",
        name: "points",
        x: points.map((p) => num((p as Record<string, unknown>).x, 0)),
        y: points.map((p) => num((p as Record<string, unknown>).y, 0)),
        text: points.map((p) => String((p as Record<string, unknown>).label || "")),
        textposition: "top center",
      });
    }
    return out;
  }, [recipe]);

  const layout = useMemo(
    () => ({
      title: { text: String(recipe?.title || "") },
      xaxis: { title: { text: String(recipe?.x_label || "x") } },
      yaxis: { title: { text: String(recipe?.y_label || "y") }, scaleanchor: "x" as const },
      showlegend: Boolean(recipe?.legend ?? true),
      paper_bgcolor: "#fff",
      plot_bgcolor: "#fff",
      margin: { t: 40, r: 20, l: 48, b: 44 },
    }),
    [recipe]
  );

  if (traces.length === 0) {
    return <div style={{ fontSize: 12, opacity: 0.7 }}>Plot recipe is present, but no plottable series found.</div>;
  }
  return <Plot data={traces} layout={layout} config={{ responsive: true, displaylogo: false }} style={{ width: "100%", height: 380 }} />;
}
