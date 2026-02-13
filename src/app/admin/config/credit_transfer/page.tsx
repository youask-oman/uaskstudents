"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE_URL, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

type CreditTransferConfig = {
  credit_transfer_enabled: boolean;
  notifications_enabled: boolean;
  min_transfer: number;
  max_transfer: number;
  daily_cap: number;
  pending_expiry_days: number;
  per_minute_limit: number;
  thank_per_minute_limit: number;
  account_age_minutes_min: number;
};

const defaultConfig: CreditTransferConfig = {
  credit_transfer_enabled: false,
  notifications_enabled: true,
  min_transfer: 1,
  max_transfer: 1000,
  daily_cap: 5000,
  pending_expiry_days: 30,
  per_minute_limit: 10,
  thank_per_minute_limit: 5,
  account_age_minutes_min: 0,
};

function num(value: string, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export default function CreditTransferConfigPage() {
  const { pushToast } = useToast();
  const [config, setConfig] = useState<CreditTransferConfig>(defaultConfig);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const baseUrl = API_BASE_URL;
  const fallbackUrl = process.env.NEXT_PUBLIC_API_FALLBACK_URL || API_BASE_URL || "http://localhost:9000";

  const adminFetch = useCallback(async (path: string, init?: RequestInit) => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    const headers: HeadersInit = {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    };

    const candidates = Array.from(
      new Set([baseUrl, fallbackUrl, "http://localhost:9000", "http://127.0.0.1:9000"].map((x) => (x || "").trim()).filter(Boolean)),
    );

    let lastErr: unknown = null;
    for (const candidate of candidates) {
      try {
        const res = await fetch(`${candidate}${path}`, { ...init, headers });
        if (res.status === 404 || res.status >= 500) continue;
        return res;
      } catch (err) {
        lastErr = err;
      }
    }
    if (lastErr) throw lastErr;
    throw new Error("API endpoint not reachable");
  }, [baseUrl, fallbackUrl]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminFetch("/api/v1/admin/config/credit_transfer");
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      const data = (await res.json()) as CreditTransferConfig;
      setConfig(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load credit transfer config");
    } finally {
      setLoading(false);
    }
  }, [adminFetch]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: CreditTransferConfig = {
        credit_transfer_enabled: Boolean(config.credit_transfer_enabled),
        notifications_enabled: Boolean(config.notifications_enabled),
        min_transfer: Math.max(0, num(String(config.min_transfer), 1)),
        max_transfer: Math.max(0, num(String(config.max_transfer), 1000)),
        daily_cap: Math.max(0, num(String(config.daily_cap), 5000)),
        pending_expiry_days: Math.max(1, Math.floor(num(String(config.pending_expiry_days), 30))),
        per_minute_limit: Math.max(1, Math.floor(num(String(config.per_minute_limit), 10))),
        thank_per_minute_limit: Math.max(1, Math.floor(num(String(config.thank_per_minute_limit), 5))),
        account_age_minutes_min: Math.max(0, Math.floor(num(String(config.account_age_minutes_min), 0))),
      };
      if (payload.max_transfer < payload.min_transfer) {
        throw new Error("max_transfer must be greater than or equal to min_transfer.");
      }
      const res = await adminFetch("/api/v1/admin/config/credit_transfer", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      const data = (await res.json()) as CreditTransferConfig;
      setConfig(data);
      pushToast({ type: "success", title: "Saved", message: "Credit transfer configuration updated." });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save credit transfer config";
      setError(message);
      pushToast({ type: "error", title: "Save failed", message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto w-full flex flex-col gap-6">
      <header className="space-y-2">
        <p className="text-sm uppercase tracking-[0.35em] text-slate-400">Admin</p>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Credit Transfer Configuration</h1>
        <p className="text-sm text-slate-500">Enable or tune transfer limits and notification behavior.</p>
      </header>

      {error && (
        <div className="rounded-lg border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#111827] p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        <label className="flex items-center justify-between rounded-lg border border-slate-200 dark:border-slate-700 px-4 py-3 md:col-span-2">
          <div>
            <p className="text-sm font-semibold">Enable Credit Transfer</p>
            <p className="text-xs text-slate-500">Master switch for sending credits between users.</p>
          </div>
          <input
            type="checkbox"
            checked={config.credit_transfer_enabled}
            onChange={(e) => setConfig((prev) => ({ ...prev, credit_transfer_enabled: e.target.checked }))}
            disabled={loading || saving}
            className="h-5 w-5"
          />
        </label>

        <label className="flex items-center justify-between rounded-lg border border-slate-200 dark:border-slate-700 px-4 py-3 md:col-span-2">
          <div>
            <p className="text-sm font-semibold">Enable Notifications</p>
            <p className="text-xs text-slate-500">In-app notifications for transfer sent/received/claimed.</p>
          </div>
          <input
            type="checkbox"
            checked={config.notifications_enabled}
            onChange={(e) => setConfig((prev) => ({ ...prev, notifications_enabled: e.target.checked }))}
            disabled={loading || saving}
            className="h-5 w-5"
          />
        </label>

        <Field label="Min Transfer" value={config.min_transfer} step="0.01" onChange={(v) => setConfig((p) => ({ ...p, min_transfer: v }))} disabled={loading || saving} />
        <Field label="Max Transfer" value={config.max_transfer} step="0.01" onChange={(v) => setConfig((p) => ({ ...p, max_transfer: v }))} disabled={loading || saving} />
        <Field label="Daily Cap" value={config.daily_cap} step="0.01" onChange={(v) => setConfig((p) => ({ ...p, daily_cap: v }))} disabled={loading || saving} />
        <Field label="Pending Expiry Days" value={config.pending_expiry_days} step="1" onChange={(v) => setConfig((p) => ({ ...p, pending_expiry_days: Math.floor(v) }))} disabled={loading || saving} />
        <Field label="Per-Minute Limit" value={config.per_minute_limit} step="1" onChange={(v) => setConfig((p) => ({ ...p, per_minute_limit: Math.floor(v) }))} disabled={loading || saving} />
        <Field label="Thank/Min Limit" value={config.thank_per_minute_limit} step="1" onChange={(v) => setConfig((p) => ({ ...p, thank_per_minute_limit: Math.floor(v) }))} disabled={loading || saving} />
        <Field label="Min Account Age (minutes)" value={config.account_age_minutes_min} step="1" onChange={(v) => setConfig((p) => ({ ...p, account_age_minutes_min: Math.floor(v) }))} disabled={loading || saving} />
      </section>

      <div className="flex items-center gap-3">
        <button
          onClick={save}
          disabled={loading || saving}
          className="px-4 py-2 rounded-lg bg-admin-primary text-white text-sm font-semibold disabled:opacity-60"
        >
          {saving ? "Saving..." : "Save Configuration"}
        </button>
        <button
          onClick={() => void load()}
          disabled={loading || saving}
          className="px-4 py-2 rounded-lg border border-slate-300 dark:border-slate-700 text-sm font-semibold"
        >
          Refresh
        </button>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  step,
  disabled,
}: {
  label: string;
  value: number;
  onChange: (next: number) => void;
  step: string;
  disabled?: boolean;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-xs uppercase tracking-wider text-slate-500">{label}</span>
      <input
        type="number"
        value={Number.isFinite(value) ? value : 0}
        step={step}
        onChange={(e) => onChange(num(e.target.value, 0))}
        disabled={disabled}
        className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2"
      />
    </label>
  );
}

