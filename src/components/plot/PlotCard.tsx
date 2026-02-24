"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import PlotFromRecipe from "@/components/plot/PlotFromRecipe";

type PlotPayload = Record<string, unknown>;

interface Props {
  plot: PlotPayload | null;
  attemptId?: string;
  playbackVisible: boolean;
  widthPx?: number;
  heightPx?: number;
}

interface PlotRenderResponse {
  cache_key: string;
  svg: string;
  meta: {
    render_ms: number;
    cached: boolean;
    warnings: string[];
  };
}

export default function PlotCard({
  plot,
  attemptId,
  playbackVisible,
  widthPx = 900,
  heightPx = 520,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [svg, setSvg] = useState<string>("");
  const [meta, setMeta] = useState<PlotRenderResponse["meta"] | null>(null);
  const [fallbackToClient, setFallbackToClient] = useState(false);

  const recipe = (plot?.recipe as Record<string, unknown>) || null;
  const shouldVisualize = Boolean(plot?.should_visualize ?? true);

  useEffect(() => {
    if (!playbackVisible || !recipe || !shouldVisualize) return;
    let cancelled = false;

    const run = async () => {
      setFallbackToClient(false);

      setLoading(true);
      setError("");
      try {
        const res = await fetch("/api/v1/plot/render-svg", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            attempt_id: attemptId || null,
            plot,
            render_options: { width_px: widthPx, height_px: heightPx, font_scale: 1.0 },
          }),
        });
        if (!res.ok) {
          if (res.status === 404 || res.status === 405 || res.status === 422 || res.status === 500 || res.status === 501 || res.status === 503) {
            if (!cancelled) {
              setFallbackToClient(true);
              setError("");
              setLoading(false);
            }
            return;
          }
          const txt = await res.text();
          throw new Error(txt || `render_failed_${res.status}`);
        }
        const body = (await res.json()) as PlotRenderResponse;
        if (cancelled) return;
        setSvg(body.svg);
        setMeta(body.meta);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Plot render failed");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [attemptId, playbackVisible, plot, recipe, shouldVisualize, widthPx, heightPx]);

  if (!playbackVisible || !recipe || !shouldVisualize) return null;

  if (loading) {
    return (
      <div style={{ border: "1px solid #dbeafe", background: "#f8fafc", borderRadius: 10, padding: 12, fontSize: 13, opacity: 0.8 }}>
        Rendering plot...
      </div>
    );
  }

  if (error) {
    return <div style={{ fontSize: 12, color: "#b91c1c" }}>Plot rendering failed: {error}</div>;
  }

  if (fallbackToClient && recipe) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <div style={{ fontSize: 11, opacity: 0.65 }}>Server SVG renderer unavailable, using client fallback.</div>
        <PlotFromRecipe recipe={recipe} />
      </div>
    );
  }

  if (!svg) {
    return <div style={{ fontSize: 12, opacity: 0.7 }}>Plot data available, waiting for renderer.</div>;
  }

  const svgDataUrl = `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <Image
        src={svgDataUrl}
        alt="Rendered plot"
        width={widthPx}
        height={heightPx}
        unoptimized
        style={{ width: "100%", maxWidth: widthPx, border: "1px solid #e2e8f0", borderRadius: 8, background: "#fff" }}
      />
      {meta ? (
        <div style={{ fontSize: 11, opacity: 0.65 }}>
          render: {meta.render_ms}ms | cache: {meta.cached ? "hit" : "miss"}
        </div>
      ) : null}
    </div>
  );
}
