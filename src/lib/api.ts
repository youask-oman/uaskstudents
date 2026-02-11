"use client";

export const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000";

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
        return "Your plan doesn’t include this tier. Please choose a different tier or upgrade.";
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
