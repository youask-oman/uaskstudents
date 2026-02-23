"use client";

import React from "react";
import DOMPurify from "dompurify";

type MathSvgProps = {
  tex: string;
  display: boolean;
  className?: string;
};

type RenderState =
  | { status: "idle" | "loading"; svg?: string; error?: string }
  | { status: "ready"; svg: string }
  | { status: "error"; error: string };

const responseCache = new Map<string, string>();

function cacheKey(tex: string, display: boolean): string {
  return `${display ? "D" : "I"}::${tex.trim()}`;
}

export default function MathSvg({ tex, display, className }: MathSvgProps) {
  const key = cacheKey(tex, display);
  const [state, setState] = React.useState<RenderState>(() => {
    const hit = responseCache.get(key);
    return hit ? { status: "ready", svg: hit } : { status: "idle" };
  });

  React.useEffect(() => {
    const hit = responseCache.get(key);
    if (hit) {
      setState({ status: "ready", svg: hit });
      return;
    }

    const controller = new AbortController();
    setState({ status: "loading" });

    fetch("/api/v1/math/svg", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tex, display }),
      signal: controller.signal,
    })
      .then(async (res) => {
        const json = await res.json();
        if (!json?.ok || typeof json.svg !== "string") {
          throw new Error(String(json?.error || "Math SVG render failed."));
        }
        return json.svg as string;
      })
      .then((svgRaw) => {
        // MathJax uses xlink:href and specific IDs. We must allow these.
        const sanitized = DOMPurify.sanitize(svgRaw, {
          USE_PROFILES: { svg: true, svgFilters: true },
          ADD_ATTR: ["xlink:href", "xmlns:xlink", "target"],
          ADD_TAGS: ["use"],
        });
        responseCache.set(key, sanitized);
        setState({ status: "ready", svg: sanitized });
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        const message = error instanceof Error ? error.message : "Math SVG render failed.";
        setState({ status: "error", error: message });
      });

    return () => controller.abort();
  }, [display, key, tex]);

  if (state.status === "error") {
    return (
      <span
        className={className}
        style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", whiteSpace: "pre-wrap" }}
      >
        {tex}
      </span>
    );
  }

  if (state.status !== "ready") {
    return (
      <span className={className} style={{ opacity: 0.6 }}>
        ...
      </span>
    );
  }

  if (display) {
    return (
      <span
        className={className}
        style={{ display: "block", overflowX: "auto", maxWidth: "100%", color: "inherit", fill: "currentColor" }}
        dangerouslySetInnerHTML={{ __html: state.svg }}
      />
    );
  }

  return (
    <span
      className={className}
      style={{ display: "inline-block", verticalAlign: "middle", color: "inherit", fill: "currentColor" }}
      dangerouslySetInnerHTML={{ __html: state.svg }}
    />
  );
}
