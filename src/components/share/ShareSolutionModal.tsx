"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useToastOptional } from "@/components/ui/ToastProvider";

type ShareVisibility = "PRIVATE" | "PUBLIC";

interface ShareStateResponse {
  attempt_id: string;
  visibility: ShareVisibility;
  share_url: string | null;
  revoked: boolean;
}

interface ShareSolutionModalProps {
  open: boolean;
  attemptId?: string | null;
  sessionId?: string | number | null;
  onClose: () => void;
}

export default function ShareSolutionModal({
  open,
  attemptId,
  sessionId,
  onClose,
}: ShareSolutionModalProps) {
  const toast = useToastOptional();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [state, setState] = useState<ShareStateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resolvedAttemptId, setResolvedAttemptId] = useState<string | null>(null);

  const effectiveAttemptId = attemptId || resolvedAttemptId || null;

  const selectedVisibility: ShareVisibility = state?.visibility || "PRIVATE";
  const shareUrl = state?.share_url || "";

  useEffect(() => {
    if (!open) return;
    const token = localStorage.getItem("token");
    if (!token) {
      setError("Please log in to share.");
      setState(null);
      return;
    }
    setLoading(true);
    setError(null);
    const load = async () => {
      let targetAttemptId = attemptId || null;
      if (!targetAttemptId && sessionId !== undefined && sessionId !== null && String(sessionId).trim()) {
        const resolveResp = await fetch(`/api/v1/shares/session/${encodeURIComponent(String(sessionId))}/attempt`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!resolveResp.ok) {
          throw new Error("Unable to resolve share attempt.");
        }
        const resolved = (await resolveResp.json()) as { attempt_id?: string | null };
        targetAttemptId = resolved.attempt_id || null;
        setResolvedAttemptId(targetAttemptId);
      }
      if (!targetAttemptId) {
        setState(null);
        setError("Solve must complete first.");
        return;
      }
      const res = await fetch(`/api/v1/shares/attempt/${encodeURIComponent(targetAttemptId)}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload?.detail || "Unable to load share state.");
      }
      const payload = (await res.json()) as ShareStateResponse;
      setState(payload);
      setResolvedAttemptId(payload.attempt_id || targetAttemptId);
    };
    void load()
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load share state."))
      .finally(() => setLoading(false));
  }, [open, attemptId, sessionId]);

  const updateVisibility = async (visibility: ShareVisibility) => {
    if (!effectiveAttemptId) {
      setError("Solve must complete first.");
      return;
    }
    const token = localStorage.getItem("token");
    if (!token) {
      setError("Please log in to share.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/shares/attempt/${encodeURIComponent(effectiveAttemptId)}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ visibility }),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload?.detail || "Unable to update share settings.");
      }
      const payload = (await res.json()) as ShareStateResponse;
      setState(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update share settings.");
    } finally {
      setSaving(false);
    }
  };

  const copyLink = async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      toast?.pushToast({
        type: "success",
        title: "Link copied",
        message: "Share link copied to clipboard.",
      });
    } catch {
      toast?.pushToast({
        type: "error",
        title: "Copy failed",
        message: "Could not copy share link.",
      });
    }
  };

  const content = useMemo(() => {
    if (loading) return "Loading share settings...";
    if (error) return error;
    return "Choose private or public sharing for this solution.";
  }, [error, loading]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[3000] bg-black/70 backdrop-blur-sm p-4 flex items-center justify-center">
      <div
        className="w-full max-w-md bg-[#2d1e16] border-4 border-[#4a3528] p-7 text-stone-100 shadow-2xl"
        style={{ borderRadius: "15px 225px 25px 255px/225px 25px 255px 25px" }}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-3xl font-semibold">Share Solution</h2>
          <button
            type="button"
            className="p-2 rounded-full hover:bg-white/10"
            aria-label="Close share dialog"
            onClick={onClose}
          >
            <span className="material-symbols-outlined text-orange-400">close</span>
          </button>
        </div>

        <p className="text-sm text-stone-300 mb-5">{content}</p>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <button
            type="button"
            disabled={loading || saving || (!effectiveAttemptId && !sessionId)}
            onClick={() => void updateVisibility("PRIVATE")}
            className={`p-4 border-2 text-center transition ${selectedVisibility === "PRIVATE"
              ? "bg-stone-700/70 border-stone-300"
              : "border-stone-600 hover:border-stone-400"
              }`}
            style={{ borderRadius: "120px 15px 100px 15px/15px 100px 15px 120px" }}
          >
            <span className="material-symbols-outlined block text-2xl mb-1">lock</span>
            <span className="font-semibold">Private</span>
          </button>
          <button
            type="button"
            disabled={loading || saving || (!effectiveAttemptId && !sessionId)}
            onClick={() => void updateVisibility("PUBLIC")}
            className={`p-4 text-center transition ${selectedVisibility === "PUBLIC"
              ? "bg-yellow-300 text-stone-900 border-2 border-yellow-200"
              : "border-2 border-stone-600 hover:border-stone-400"
              }`}
            style={{ borderRadius: "12px 28px 16px 28px / 28px 16px 28px 12px" }}
          >
            <span className="material-symbols-outlined block text-2xl mb-1">public</span>
            <span className="font-semibold">Public</span>
          </button>
        </div>

        <div className="mb-6">
          <label className="block text-sm text-stone-200 mb-2">Shareable Link</label>
          <div className="flex items-center gap-2 p-3 border-2 border-dashed border-stone-600 bg-black/30"
            style={{ borderRadius: "255px 25px 225px 25px/25px 225px 25px 255px" }}>
            <input
              readOnly
              value={selectedVisibility === "PUBLIC" ? shareUrl : ""}
              placeholder={selectedVisibility === "PUBLIC" ? "Generating link..." : "Private mode: no public link"}
              className="flex-1 bg-transparent text-xs text-stone-200 outline-none"
            />
            <button
              type="button"
              onClick={() => void copyLink()}
              disabled={loading || selectedVisibility !== "PUBLIC" || !shareUrl}
              className="px-3 py-1 text-sm border border-orange-400/50 text-orange-300 rounded-md disabled:opacity-40"
            >
              Copy Link
            </button>
          </div>
        </div>

        <div className="flex items-start gap-2 text-xs text-stone-300">
          <span className="material-symbols-outlined text-orange-400 text-base">info</span>
          <p>
            Do not share personal information. Sharing publicly lets anyone with the link view this solution. See{" "}
            <Link href="/legal/terms" className="underline">
              Terms of Service
            </Link>.
          </p>
        </div>
      </div>
    </div>
  );
}
