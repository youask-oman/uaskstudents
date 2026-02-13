"use client";

import React from "react";
import dynamic from "next/dynamic";
import { Config, Data, Layout } from "plotly.js";
import { GraphSpec } from "@/components/workspace/graph_spec";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface PlotlyGraphProps {
  spec: GraphSpec;
  height?: number;
}

export default function PlotlyGraph({ spec, height = 400 }: PlotlyGraphProps) {
  const data: Data[] = spec.traces.map((t) => {
    const trace: Record<string, unknown> = {
      name: t.name,
      showlegend: t.show_legend ?? true,
    };

    if (t.kind === "scatter") {
      trace.type = "scatter";
      trace.x = t.x;
      trace.y = t.y;
      trace.mode = t.mode || "lines";
      trace.line = { width: 2.5, shape: "spline", smoothing: 1.3, ...t.line_style };
      trace.connectgaps = false;
    } else if (t.kind === "surface") {
      trace.type = "surface";
      trace.x = t.x;
      trace.y = t.y;
      trace.z = t.z_matrix;
      trace.colorscale = "Viridis";
      trace.showscale = false;
    } else if (t.kind === "contour") {
      trace.type = "contour";
      trace.x = t.x;
      trace.y = t.y;
      trace.z = t.z_matrix;
      trace.showscale = false;
      trace.line = { width: 3, color: "#3b82f6", ...t.line_style };
    } else if (t.kind === "scatter3d") {
      trace.type = "scatter3d";
      trace.x = t.x;
      trace.y = t.y;
      trace.z = t.z;
      trace.mode = t.mode || "lines";
      trace.line = { width: 4, ...t.line_style };
    }

    return trace as Data;
  });

  if (spec.key_points.length > 0) {
    data.push({
      type: spec.graph_type.startsWith("3d") ? "scatter3d" : "scatter",
      x: spec.key_points.map((p) => p.x),
      y: spec.key_points.map((p) => p.y),
      z: spec.key_points.map((p) => p.z),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      mode: "markers+text" as any,
      name: "Key Points",
      text: spec.key_points.map((p) => p.label),
      textposition: "top center",
      marker: { size: 8, color: "#ef4444" },
      showlegend: false,
    } as Data);
  }

  const layout: Partial<Layout> = {
    autosize: true,
    height,
    title: { text: spec.title || "", font: { size: 14, color: "#64748b" } },
    margin: { l: 50, r: 30, t: 50, b: 50 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(255,255,255,0.8)",
    xaxis: {
      title: { text: spec.axes.x_label },
      gridcolor: "#f1f5f9",
      zerolinecolor: "#94a3b8",
      zerolinewidth: 1.5,
      range: spec.axes.x_range,
      scaleanchor: spec.axes.equal_aspect ? "y" : undefined,
    },
    yaxis: {
      title: { text: spec.axes.y_label },
      gridcolor: "#f1f5f9",
      zerolinecolor: "#94a3b8",
      zerolinewidth: 1.5,
      range: spec.axes.y_range,
    },
    font: { family: "Inter, sans-serif" },
  };

  const config: Partial<Config> = {
    responsive: true,
    displayModeBar: "hover",
    modeBarButtonsToRemove: ["lasso2d", "select2d", "zoomIn2d", "zoomOut2d", "autoScale2d"],
    displaylogo: false,
  };

  return <Plot data={data} layout={layout} config={config} style={{ width: "100%", height: "100%" }} useResizeHandler />;
}

