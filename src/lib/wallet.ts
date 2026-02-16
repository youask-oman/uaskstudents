"use client";

import { getAuthToken, parseApiError, ApiError, fetchApi } from "@/lib/api";
import {
    CreditsBalanceSchema,
    CreditsLedgerPageSchema,
    CreditsLotsPageSchema,
} from "@/lib/contracts";

export type WalletSummary = {
    user_id: number;
    available_credits: number;
    spendable_balance: number;
    cached_balance: number;
    computed_balance: number;
    delta: number;
    pending_holds: number;
    pending_hold_credits: number;
    expiring_soon_credits: number;
    expiring_soon_lots: number;
    entitlements: Record<string, unknown>;
    effective_tier: "SHORT_STEPS" | "FINAL" | "STANDARD" | "RESEARCH";
    active_programs: string[];
};

export type WalletTier = "SHORT_STEPS" | "FINAL" | "STANDARD" | "RESEARCH";

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

function resolveEffectiveBalance(data: {
    available_credits?: number;
    spendable_balance?: number;
}): { available: number; spendable: number; effective: number } {
    const available = Number(data.available_credits || 0);
    const spendable = Number(data.spendable_balance || 0);
    const effective = spendable > 0 || available <= 0 ? spendable : available;
    return { available, spendable, effective };
}

export async function fetchWalletSummary(): Promise<WalletSummary> {
    const res = await fetchApi(`/api/v1/credits/balance`, {
        headers: getAuthHeaders(),
    });
    if (!res.ok) {
        const err = await parseApiError(res);
        throw toApiError(err);
    }
    const data = CreditsBalanceSchema.parse(await res.json());
    const balance = resolveEffectiveBalance(data);
    const effectiveTier = (typeof window !== "undefined" ? (localStorage.getItem("uask.solveTier") || "STANDARD") : "STANDARD") as WalletTier;
    return {
        user_id: data.user_id,
        available_credits: balance.available,
        spendable_balance: balance.spendable,
        cached_balance: balance.available,
        computed_balance: balance.effective,
        delta: balance.available - balance.effective,
        pending_holds: 0,
        pending_hold_credits: Number(data.reserved_credits || 0),
        expiring_soon_credits: Number(data.expiring_soon_credits || 0),
        expiring_soon_lots: Number(data?.lots_summary?.active_lots || 0),
        entitlements: {},
        effective_tier: effectiveTier,
        active_programs: [],
    } as WalletSummary;
}

function mapWalletTierToApi(tier: WalletTier): string {
    return String(tier || "STANDARD").toLowerCase();
}

export async function updateWalletTier(tier: WalletTier): Promise<{ subscription_tier: string; effective_tier: WalletTier | string }> {
    const res = await fetchApi(`/api/v1/wallet/tier`, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
            ...(getAuthHeaders() || {}),
        },
        body: JSON.stringify({ tier: mapWalletTierToApi(tier) }),
    });
    if (!res.ok) {
        const err = await parseApiError(res);
        throw toApiError(err);
    }
    return (await res.json()) as { subscription_tier: string; effective_tier: WalletTier | string };
}

export async function fetchWalletLots(limit = 20, offset = 0): Promise<PaginatedResponse<WalletLot>> {
    const params = new URLSearchParams({ limit: String(limit) });
    const res = await fetchApi(`/api/v1/credits/lots?${params.toString()}`, {
        headers: getAuthHeaders(),
    });
    if (!res.ok) {
        const err = await parseApiError(res);
        throw toApiError(err);
    }
    const data = CreditsLotsPageSchema.parse(await res.json());
    type CreditsLotRow = {
        lot_id: string;
        source?: string;
        credits_total?: number;
        credits_remaining?: number;
        expires_at?: string | null;
        created_at: string;
    };
    const items = Array.isArray(data.items)
        ? data.items.map((row: CreditsLotRow, idx: number) => ({
            id: idx + 1,
            lot_type: row.source,
            credits_total: Number(row.credits_total || 0),
            credits_remaining: Number(row.credits_remaining || 0),
            status: "ACTIVE",
            expires_at: row.expires_at || null,
            created_at: row.created_at,
            source_label: row.source,
            source_meta: { lot_id: row.lot_id },
        }))
        : [];
    return { items, total: items.length, limit, offset };
}

export async function fetchWalletLedger(limit = 20, offset = 0): Promise<PaginatedResponse<WalletLedgerEntry>> {
    const params = new URLSearchParams({ limit: String(limit) });
    const res = await fetchApi(`/api/v1/credits/ledger?${params.toString()}`, {
        headers: getAuthHeaders(),
    });
    if (!res.ok) {
        const err = await parseApiError(res);
        throw toApiError(err);
    }
    const data = CreditsLedgerPageSchema.parse(await res.json());
    type CreditsLedgerRow = {
        action: string;
        outcome?: string;
        total_cost?: number;
        request_id?: string | null;
        created_at: string;
    };
    const items = Array.isArray(data.items)
        ? data.items.map((row: CreditsLedgerRow, idx: number) => ({
            id: idx + 1,
            event_type: row.action,
            status: row.outcome,
            credits_delta: -Number(row.total_cost || 0),
            credits_before: 0,
            credits_after: 0,
            reference: row.request_id,
            request_id: row.request_id,
            created_at: row.created_at,
        }))
        : [];
    return { items, total: items.length, limit, offset };
}

export async function fetchWalletPrograms(limit = 50, offset = 0): Promise<PaginatedResponse<WalletProgramEnrollment>> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    const res = await fetchApi(`/api/v1/wallet/programs?${params.toString()}`, {
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
    max_questions_allowed?: number | null;
    breakdown:
    | {
        tier_base?: number;
        ocr?: number;
        voice?: number;
        verify?: number;
        plot?: number;
        asset_type_addon?: number;
    }
    | {
        base: number;
        reason?: string;
        addons?: Record<string, number>;
    };
    pricing_version: string;
    pricing_version_plan?: string;
    pricing_version_token_config?: number;
};

export type SolveTier = "SHORT_STEPS" | "STANDARD" | "RESEARCH" | "FINAL";
export type SolveInputType = "text" | "snap" | "voice";
export type SolveAssetType = "none" | "image" | "pdf";

function mapTierToApi(tier: SolveTier): string {
    if (tier === "SHORT_STEPS") return "short_steps";
    if (tier === "FINAL") return "final";
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
    const res = await fetchApi(`/api/v1/credits/estimate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            ...payload,
            tier: mapTierToApi(payload.tier),
            include_attempt_fee: true,
        }),
    });
    if (!res.ok) {
        const err = await parseApiError(res);
        throw toApiError(err);
    }
    return (await res.json()) as CreditsEstimateResponse;
}
