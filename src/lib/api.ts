"use client";

export const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "";

const API_FALLBACK_URL =
    process.env.NEXT_PUBLIC_API_FALLBACK_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://127.0.0.1:9016";

export const getAuthToken = () =>
    typeof window !== "undefined" ? localStorage.getItem("token") : null;

export type ApiError = {
    message: string;
    requestId?: string;
    code?: string;
    details?: unknown;
    status?: number;
};

const friendlyMessage = (code?: string, rawMessage?: string) => {
    const message = rawMessage || "Request failed.";
    const normalized = message.toLowerCase();

    if (code === "CAP_EXCEEDED" || normalized.includes("daily credit limit")) {
        return "You've reached your daily credit limit. Please try again tomorrow or top up.";
    }
    if (code === "INSUFFICIENT_CREDITS" || normalized.includes("insufficient credits")) {
        return "You don't have enough credits to solve this. Please top up to continue.";
    }
    if (code === "auth_required" || normalized.includes("missing token") || normalized.includes("unauthorized")) {
        return "Please log in to continue.";
    }
    if (code === "rate_limit" || normalized.includes("rate limit")) {
        return "You're doing that too fast. Please wait a moment and try again.";
    }
    if (code === "TIER_NOT_ALLOWED" || normalized.includes("tier not included")) {
        return "Your plan does not include this tier. Please choose a different tier or upgrade.";
    }
    if (code === "terms_acceptance_required" || normalized.includes("terms of service")) {
        return "You need to accept the latest Terms of Service before continuing.";
    }
    return message;
};

export async function parseApiError(res: Response): Promise<ApiError> {
    let detail: string | undefined;
    let code: string | undefined;
    let details: unknown;
    let requestId: string | undefined;
    try {
        const data = await res.json();
        if (data?.error) {
            if (typeof data.error.message === "string") detail = data.error.message;
            if (typeof data.error.code === "string") code = data.error.code;
            if (typeof data.error.request_id === "string") requestId = data.error.request_id;
            details = data.error.details;
        } else {
            if (typeof data?.detail === "string") detail = data.detail;
            else if (typeof data?.message === "string") detail = data.message;
            else if (Array.isArray(data?.detail)) detail = "Validation error";
        }
    } catch {
        detail = undefined;
    }

    requestId =
        requestId ||
        res.headers.get("x-request-id") ||
        res.headers.get("x-trace-id") ||
        undefined;

    const message = friendlyMessage(code, detail || `Request failed (${res.status})`);

    return {
        message,
        requestId,
        code,
        details,
        status: res.status,
    };
}

function buildApiCandidates(): string[] {
    return Array.from(
        new Set(
            [
                API_BASE_URL,
                API_FALLBACK_URL,
                "http://127.0.0.1:9000",
                "http://localhost:9000",
                "http://127.0.0.1:9016",
                "http://localhost:9016",
                "",
            ]
                .map((x) => (x || "").trim())
        )
    );
}

function joinApiUrl(base: string, path: string): string {
    if (!base) return path;
    return `${base}${path}`;
}

export async function fetchApi(path: string, init?: RequestInit): Promise<Response> {
    const candidates = buildApiCandidates();
    let lastErr: unknown = null;

    for (const base of candidates) {
        try {
            const res = await fetch(joinApiUrl(base, path), init);
            if (res.status === 404 || res.status >= 500) {
                continue;
            }
            return res;
        } catch (err) {
            lastErr = err;
        }
    }

    if (lastErr) throw lastErr;
    throw new Error("Network error");
}

