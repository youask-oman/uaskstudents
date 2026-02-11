"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { API_BASE_URL } from "@/lib/api";

type LegalStatus = {
  requires_terms_acceptance: boolean;
  required_terms_version?: string | null;
};

export default function TermsAcceptanceGate() {
  const pathname = usePathname();
  const router = useRouter();
  const [status, setStatus] = useState<LegalStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [accepting, setAccepting] = useState(false);

  const token = useMemo(
    () => (typeof window !== "undefined" ? localStorage.getItem("token") : null),
    [pathname]
  );

  const shouldSkip = pathname?.startsWith("/legal/") || pathname === "/login" || pathname === "/signup";

  const refreshStatus = async () => {
    if (!token || shouldSkip) {
      setStatus(null);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/legal/status`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (!res.ok) return;
      const data = (await res.json()) as LegalStatus;
      setStatus(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refreshStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, pathname]);

  const acceptTerms = async () => {
    if (!token || !status?.required_terms_version) return;
    setAccepting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/legal/accept`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          document_key: "terms_of_service",
          document_version: status.required_terms_version,
          method: "in_app_modal",
          locale: navigator.language,
        }),
      });
      if (res.ok) {
        setStatus({ requires_terms_acceptance: false, required_terms_version: status.required_terms_version });
      }
    } finally {
      setAccepting(false);
    }
  };

  if (shouldSkip || !token || loading || !status?.requires_terms_acceptance) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[100] bg-black/50 backdrop-blur-sm flex items-center justify-center px-4">
      <div className="w-full max-w-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl p-6">
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">Updated Terms of Service</h2>
        <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
          We updated our Terms of Service. You must accept the latest version to continue using your account.
        </p>
        <p className="mt-2 text-xs text-slate-500">Required version: {status.required_terms_version || "latest"}</p>
        <div className="mt-5 flex flex-wrap gap-2">
          <button
            onClick={acceptTerms}
            disabled={accepting}
            className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-semibold disabled:opacity-60"
          >
            {accepting ? "Accepting..." : "Accept"}
          </button>
          <Link href="/legal/terms" className="px-4 py-2 rounded-lg border border-slate-300 text-sm font-semibold">
            View Terms and Conditions
          </Link>
          <button
            onClick={() => {
              localStorage.removeItem("token");
              localStorage.removeItem("user");
              localStorage.removeItem("user_id");
              localStorage.removeItem("user_name");
              router.push("/login");
            }}
            className="px-4 py-2 rounded-lg border border-slate-300 text-sm font-semibold"
          >
            Logout
          </button>
        </div>
      </div>
    </div>
  );
}
