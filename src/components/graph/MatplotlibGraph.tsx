"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";

interface MatplotlibGraphProps {
  attemptId: string;
  height?: number;
  width?: number;
  onUnavailable?: (reason: string) => void;
}

const readTheme = (): "light" | "dark" => {
  if (typeof document === "undefined") return "light";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
};

export default function MatplotlibGraph({
  attemptId,
  height = 460,
  width = 1200,
  onUnavailable,
}: MatplotlibGraphProps) {
  const [broken, setBroken] = useState(false);
  const [theme] = useState<"light" | "dark">(readTheme);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState<{ width: number; height: number }>({
    width,
    height,
  });

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const w = Math.max(320, Math.round(entry.contentRect.width));
      const h = Math.max(220, Math.round(entry.contentRect.height || height));
      setSize((prev) => (prev.width === w && prev.height === h ? prev : { width: w, height: h }));
    });
    observer.observe(host);
    return () => observer.disconnect();
  }, [height]);

  const src = useMemo(() => {
    const query = new URLSearchParams({
      theme,
      width: String(size.width),
      height: String(size.height),
      rv: "3",
    });
    return `/api/v1/attempt/${encodeURIComponent(attemptId)}/graph.svg?${query.toString()}`;
  }, [attemptId, size.height, size.width, theme]);

  if (broken) return null;

  return (
    <div
      ref={hostRef}
      style={{ width: "100%", height: `${height}px`, display: "flex", alignItems: "stretch", justifyContent: "stretch" }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt="Math graph"
        loading="lazy"
        style={{ width: "100%", height: "100%", objectFit: "fill", display: "block", margin: "0" }}
        onError={() => {
          setBroken(true);
          onUnavailable?.("matplotlib_asset_unavailable");
        }}
      />
    </div>
  );
}
