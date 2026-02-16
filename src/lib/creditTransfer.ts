"use client";

import { getAuthToken, parseApiError, ApiError, fetchApi } from "@/lib/api";

export type CreditTransferBalance = {
    spendable_balance: number;
    pending_outgoing_total: number;
    can_transfer: boolean;
    min_transfer: number;
    max_transfer: number;
    daily_remaining: number;
    reason_if_disabled?: string | null;
    credit_transfer_enabled: boolean;
};

export type CreditTransferResult = {
    transfer_id: string;
    status: string;
    amount: number;
    recipient_email: string;
    recipient_user_id?: number | null;
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

export async function fetchTransferBalance(): Promise<CreditTransferBalance> {
    const res = await fetchApi(`/api/v1/credits/balance`, {
        headers: authHeaders(),
    });
    if (!res.ok) {
        const err = await parseApiError(res);
        throw toApiError(err);
    }
    return (await res.json()) as CreditTransferBalance;
}

export async function transferCredits(payload: {
    recipient_email: string;
    amount: number;
    idempotency_key: string;
}): Promise<CreditTransferResult> {
    const res = await fetchApi(`/api/v1/credits/transfer`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...authHeaders(),
        },
        body: JSON.stringify(payload),
    });
    if (!res.ok) {
        const err = await parseApiError(res);
        throw toApiError(err);
    }
    return (await res.json()) as CreditTransferResult;
}

export async function claimPendingCredits(): Promise<{ claimed_count: number; transfer_ids: string[] }> {
    const res = await fetchApi(`/api/v1/credits/claim_pending`, {
        method: "POST",
        headers: authHeaders(),
    });
    if (!res.ok) {
        const err = await parseApiError(res);
        throw toApiError(err);
    }
    return (await res.json()) as { claimed_count: number; transfer_ids: string[] };
}

