"use client";

import { API_BASE_URL, getAuthToken, parseApiError, ApiError } from "@/lib/api";

export type WalletSummary = {
    user_id: number;
    cached_balance: number;
    computed_balance: number;
    delta: number;
    pending_holds: number;
    pending_hold_credits: number;
    expiring_soon_credits: number;
    expiring_soon_lots: number;
    entitlements: Record<string, unknown>;
    effective_tier: "FREE" | "STANDARD" | "RESEARCH";
    active_programs: string[];
};

export type WalletLot = {
    id: number;
    lot_type?: string | null;
    credits_total: number;
    credits_remaining: number;
    status: string;
    expires_at?: string | null;
    created_at: string;
    source_label?: string | null;
    source_meta?: Record<string, unknown> | null;
};

export type WalletLedgerEntry = {
    id: number;
    event_type: string;
    status?: string | null;
    credits_delta: number;
    credits_before: number;
    credits_after: number;
    reference?: string | null;
    request_id?: string | null;
    created_at: string;
};

export type WalletProgramEnrollment = {
    id: number;
    program_id: number;
    program_name?: string | null;
    program_slug?: string | null;
    status: string;
    started_at: string;
    ended_at?: string | null;
    last_grant_month?: string | null;
    next_grant_date?: string | null;
    next_grant_status?: string | null;
    monthly_gift_credits?: number | null;
    gift_expiry_window_days?: number | null;
    entitlements?: Record<string, unknown> | null;
};

export type PaginatedResponse<T> = {
    items: T[];
    total: number;
    limit: number;
    offset: number;
};

const getAuthHeaders = (): HeadersInit | undefined => {
    const token = getAuthToken();
    return token ? { Authorization: `Bearer ${token}` } : undefined;
};

const toApiError = (err: ApiError) => {
    const error = new Error(err.message) as Error & { requestId?: string };
    error.requestId = err.requestId;
    return error;
};

export async function fetchWalletSummary(): Promise<WalletSummary> {
    const res = await fetch(`${API_BASE_URL}/api/v1/wallet/summary`, {
        headers: getAuthHeaders(),
    });
    if (!res.ok) {
        const err = await parseApiError(res);
        throw toApiError(err);
    }
    return (await res.json()) as WalletSummary;
}

export async function fetchWalletLots(limit = 20, offset = 0): Promise<PaginatedResponse<WalletLot>> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    const res = await fetch(`${API_BASE_URL}/api/v1/wallet/lots?${params.toString()}`, {
        headers: getAuthHeaders(),
    });
    if (!res.ok) {
        const err = await parseApiError(res);
        throw toApiError(err);
    }
    return (await res.json()) as PaginatedResponse<WalletLot>;
}

export async function fetchWalletLedger(limit = 20, offset = 0): Promise<PaginatedResponse<WalletLedgerEntry>> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    const res = await fetch(`${API_BASE_URL}/api/v1/wallet/ledger?${params.toString()}`, {
        headers: getAuthHeaders(),
    });
    if (!res.ok) {
        const err = await parseApiError(res);
        throw toApiError(err);
    }
    return (await res.json()) as PaginatedResponse<WalletLedgerEntry>;
}

export async function fetchWalletPrograms(limit = 50, offset = 0): Promise<PaginatedResponse<WalletProgramEnrollment>> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    const res = await fetch(`${API_BASE_URL}/api/v1/wallet/programs?${params.toString()}`, {
        headers: getAuthHeaders(),
    });
    if (!res.ok) {
        const err = await parseApiError(res);
        throw toApiError(err);
    }
    return (await res.json()) as PaginatedResponse<WalletProgramEnrollment>;
}

export type CreditsEstimateResponse = {
    total_credits: number;
    per_question_credits: number;
    breakdown: {
        tier_base: number;
        ocr: number;
        voice: number;
        verify?: number;
        plot?: number;
        asset_type_addon?: number;
    };
    pricing_version: string;
    pricing_version_plan?: string;
    pricing_version_token_config?: number;
};

export type SolveTier = "FREE" | "STANDARD" | "RESEARCH" | "SHORT";
export type SolveInputType = "text" | "snap" | "voice";
export type SolveAssetType = "none" | "image" | "pdf";

function mapTierToApi(tier: SolveTier): string {
    if (tier === "FREE") return "three_step";
    return tier.toLowerCase();
}

export async function fetchCreditsEstimate(payload: {
    tier: SolveTier;
    input_type: SolveInputType;
    asset_type: SolveAssetType;
    question_count: number;
    addons: {
        ocr: boolean;
        voice: boolean;
        verify: boolean;
        plot: boolean;
    };
}): Promise<CreditsEstimateResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/credits/estimate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            ...payload,
            tier: mapTierToApi(payload.tier),
        }),
    });
    if (!res.ok) {
        const err = await parseApiError(res);
        throw toApiError(err);
    }
    return (await res.json()) as CreditsEstimateResponse;
}
