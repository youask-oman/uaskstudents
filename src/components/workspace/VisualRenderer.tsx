"use client";

import React, { useState } from "react";
import MatplotlibGraph from "@/components/graph/MatplotlibGraph";
import PlotlyGraph from "@/components/graph/PlotlyGraph";
import { GraphSpec } from "./graph_spec";

interface VisualRendererProps {
  visual: GraphSpec | Record<string, unknown>;
  height?: number;
  attemptId?: string | null;
  strictAsset?: boolean;
}

const asFiniteNumber = (value: unknown): number | null => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const normalizeSpec = (visual: GraphSpec | Record<string, unknown>): GraphSpec | null => {
  const isHydrated = (visual as GraphSpec).graph_type !== undefined;
  const legacyVisual = visual as Record<string, unknown>;
  const isMapped =
    legacyVisual.axes !== undefined ||
    legacyVisual.series !== undefined ||
    legacyVisual.traces !== undefined ||
    legacyVisual.kind !== undefined;

  if (!isHydrated && !isMapped) return null;
  if (isHydrated) return visual as GraphSpec;

  const legacy = visual as Record<string, unknown>;
  const axes = legacy.axes as Record<string, unknown> | undefined;
  const domain = legacy.domain as Record<string, unknown> | undefined;
  const traces = (legacy.traces || legacy.series) as Array<Record<string, unknown>> | undefined;
  const markers = (legacy.markers || legacy.key_points) as Array<Record<string, unknown>> | undefined;

  const normalizedTraces =
    traces?.map((s) => {
      const points = Array.isArray(s.points) ? (s.points as Array<Record<string, unknown>>) : [];
      const x = points.map((p) => asFiniteNumber(p.x)).filter((v): v is number => v !== null);
      const y = points.map((p) => asFiniteNumber(p.y)).filter((v): v is number => v !== null);

      return {
        name: (s.label as string) || (s.name as string) || "series",
        kind: "scatter" as const,
        x,
        y,
        expression: typeof s.expression_latex === "string" ? s.expression_latex : undefined,
        mode: (s.mode as "lines" | "markers" | "lines+markers") || "lines",
        show_legend: true,
      };
    }) || [];

  return {
    version: "1.0",
    graph_type: "2d_function",
    title: (legacy.title as string) || "",
    axes: {
      x_label: (axes?.x_label as string) || "x",
      y_label: (axes?.y_label as string) || "y",
      x_range: [
        parseFloat((domain?.x_min_latex as string) || String(domain?.x_min || "-10")),
        parseFloat((domain?.x_max_latex as string) || String(domain?.x_max || "10")),
      ],
      y_range: [
        parseFloat(String((axes?.y_range as [number, number] | undefined)?.[0] ?? domain?.y_min ?? -10)),
        parseFloat(String((axes?.y_range as [number, number] | undefined)?.[1] ?? domain?.y_max ?? 10)),
      ],
    },
    traces: normalizedTraces,
    key_points:
      markers?.map((m) => ({
        label: (m.label as string) || "",
        x: Number(m.x),
        y: Number(m.y),
      })) || [],
    warnings: [],
  };
};

export default function VisualRenderer({ visual, height = 460, attemptId, strictAsset = false }: VisualRendererProps) {
  const spec = normalizeSpec(visual);
  const [assetUnavailableReason, setAssetUnavailableReason] = useState<string | null>(null);

  if (!spec) {
    return (
      <div className="p-4 bg-slate-50 dark:bg-card-dark text-slate-500 text-sm border border-slate-200 dark:border-border-dark rounded-xl">
        Graph unavailable.
      </div>
    );
  }

  const canTryAsset = Boolean(attemptId);
  const usePlotlyFallback = strictAsset ? !canTryAsset : (!canTryAsset || assetUnavailableReason !== null);
  const wrapperClass = strictAsset
    ? "w-full bg-transparent border-0 rounded-none overflow-visible my-0"
    : "w-full rounded-xl border border-slate-300/80 dark:border-slate-600/80 overflow-hidden bg-white/60 dark:bg-slate-900/40 my-3";
  const bodyClass = strictAsset ? "p-0" : "p-2 sm:p-3";

  return (
    <div className={wrapperClass}>
      <div className={bodyClass}>
        {usePlotlyFallback ? (
          strictAsset ? (
            <div className="px-2 py-6 text-sm text-slate-500 text-center">
              Graph unavailable for this attempt.
            </div>
          ) : (
            <>
              {assetUnavailableReason ? (
                <div className="mb-2 px-2 pt-2 text-xs text-slate-500">
                  Graph asset unavailable ({assetUnavailableReason}). Showing fallback renderer.
                </div>
              ) : null}
              <PlotlyGraph spec={spec} height={height} />
            </>
          )
        ) : (
          <MatplotlibGraph
            attemptId={attemptId as string}
            height={height}
            onUnavailable={setAssetUnavailableReason}
          />
        )}
      </div>
      {spec.warnings.length > 0 && (
        <div className="px-4 py-2 bg-amber-50 dark:bg-amber-900/10 border-t border-amber-100 dark:border-amber-900/20">
          {spec.warnings.map((w, i) => (
            <p key={i} className="text-[10px] text-amber-700 dark:text-amber-400">
              Warning: {w}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
