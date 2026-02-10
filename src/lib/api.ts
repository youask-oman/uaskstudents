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
};

export async function parseApiError(res: Response): Promise<ApiError> {
    let detail: string | undefined;
    try {
        const data = await res.json();
        if (typeof data?.detail === "string") detail = data.detail;
        else if (typeof data?.message === "string") detail = data.message;
        else if (Array.isArray(data?.detail)) detail = "Validation error";
    } catch {
        detail = undefined;
    }

    const requestId =
        res.headers.get("x-request-id") ||
        res.headers.get("x-trace-id") ||
        undefined;

    const message = detail
        ? detail
        : `Request failed (${res.status})`;

    return {
        message,
        requestId,
    };
}

