"use client";

import { API_BASE_URL, getAuthToken, parseApiError, ApiError } from "@/lib/api";

export type AppNotification = {
    id: number;
    type: string;
    title: string;
    body: string;
    payload_json?: Record<string, unknown> | null;
    severity: string;
    is_read: boolean;
    created_at: string;
    read_at?: string | null;
    action_type?: string | null;
    action_payload?: Record<string, unknown> | null;
};

const toApiError = (err: ApiError) => {
    const error = new Error(err.message) as Error & { requestId?: string };
    error.requestId = err.requestId;
    return error;
};

const authHeaders = (): HeadersInit => {
    const token = getAuthToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
};

export async function fetchNotifications(cursor?: number, limit = 20): Promise<{ items: AppNotification[]; next_cursor?: number | null }> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (cursor) params.set("cursor", String(cursor));
    const res = await fetch(`${API_BASE_URL}/api/v1/notifications?${params.toString()}`, {
        headers: authHeaders(),
    });
    if (!res.ok) {
        const err = await parseApiError(res);
        throw toApiError(err);
    }
    return (await res.json()) as { items: AppNotification[]; next_cursor?: number | null };
}

export async function markNotificationRead(id: number): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/api/v1/notifications/${id}/read`, {
        method: "POST",
        headers: authHeaders(),
    });
    if (!res.ok) {
        const err = await parseApiError(res);
        throw toApiError(err);
    }
}

export async function markNotificationsReadAll(): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/api/v1/notifications/read_all`, {
        method: "POST",
        headers: authHeaders(),
    });
    if (!res.ok) {
        const err = await parseApiError(res);
        throw toApiError(err);
    }
}

