"use client";

import { useMemo, useState } from "react";

const STORAGE_KEY = "analytics_cookie_consent";

export default function AnalyticsCookieBanner() {
  const enabled = useMemo(
    () => (process.env.NEXT_PUBLIC_ENABLE_ANALYTICS_COOKIES || "").toLowerCase() === "true",
    []
  );
  const [value, setValue] = useState<"granted" | "denied" | null>(() => {
    if (!enabled || typeof window === "undefined") return null;
    return localStorage.getItem(STORAGE_KEY) as "granted" | "denied" | null;
  });
  const [visible, setVisible] = useState<boolean>(() => {
    if (!enabled || typeof window === "undefined") return false;
    return !localStorage.getItem(STORAGE_KEY);
  });

  if (!enabled || !visible) return null;

  const save = (next: "granted" | "denied") => {
    localStorage.setItem(STORAGE_KEY, next);
    setValue(next);
    setVisible(false);
  };

  return (
    <div className="fixed bottom-4 left-4 right-4 z-50 md:left-auto md:max-w-md rounded-xl border border-slate-200 bg-white p-4 shadow-xl">
      <p className="text-sm text-slate-700">
        We use analytics cookies to improve product performance. You can manage analytics cookies here.
      </p>
      <div className="mt-3 flex items-center gap-2">
        <button className="px-3 py-1.5 text-xs rounded bg-primary text-white font-semibold" onClick={() => save("granted")}>
          Enable analytics
        </button>
        <button className="px-3 py-1.5 text-xs rounded border border-slate-300 text-slate-700 font-semibold" onClick={() => save("denied")}>
          Disable analytics
        </button>
        {value && <span className="ml-auto text-[10px] uppercase tracking-widest text-slate-400">{value}</span>}
      </div>
    </div>
  );
}
