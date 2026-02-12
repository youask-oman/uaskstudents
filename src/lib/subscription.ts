/**
 * Types and API client for subscription/tier-aware solve UX.
 */

export interface TierPricing {
    text: number;
    snap_image: number;
    snap_pdf: number;
    voice: number;
}

export interface SubscriptionPlan {
    id: number;
    slug: string;
    display_name: string;
    credits_monthly: number;
    seats: number;
    // Multipliers can be legacy flat object or new structured object
    multipliers: {
        version?: number;
        credits?: {
            solve: {
                free: TierPricing;
                standard: TierPricing;
                research: TierPricing;
                short: TierPricing;
            };
            verify: {
                free: number;
                standard: number;
                research: number;
            };
            plot_trigger: number;
            plot_spec: number;
        };
        // Legacy fallback keys
        text_concise?: number;
        text_detailed?: number;
        ocr_add?: number;
        voice_add?: number;
    };
    features: Record<string, unknown>;
}

export interface SubscriptionUsage {
    credits_used: number;
    credits_remaining: number;
    credits_balance: number;
    ocr_used: number;
    ocr_limit: number;
    voice_used: number;
    voice_limit: number;
}

export interface SubscriptionProfile {
    grade_level: string | null;
    region_country: string | null;
    region_state_province: string | null;
    school_id?: number | null;
    school_name?: string | null;
    display_name: string;
}

export interface SubscriptionResponse {
    plan: SubscriptionPlan;
    usage: SubscriptionUsage;
    profile: SubscriptionProfile;
    status: string;
    current_period_start: string;
    current_period_end: string;
    allow_detailed: boolean;
    allow_ocr: boolean;
    allow_voice: boolean;
}

export type SolveTier = "FREE" | "STANDARD" | "RESEARCH" | "SHORT";
export type SolveInputType = "text" | "snap" | "voice";
export type SolveAssetType = "none" | "image" | "pdf";

export interface CreditsEstimateBreakdown {
    tier_base: number;
    ocr: number;
    voice: number;
    verify: number;
    plot: number;
    asset_type_addon?: number;
}

export interface CreditsEstimateResponse {
    total_credits: number;
    per_question_credits: number;
    breakdown: CreditsEstimateBreakdown;
    pricing_version: string;
}

/**
 * Fetch subscription details for tier-aware solve UX.
 */
export async function fetchSubscription(userId: string): Promise<SubscriptionResponse> {
    const baseUrl =
        process.env.NEXT_PUBLIC_API_BASE_URL ||
        process.env.NEXT_PUBLIC_API_URL ||
        "http://localhost:9000";
    const res = await fetch(`${baseUrl}/api/v1/users/me/subscription?user_id=${userId}`);

    if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || "Subscription fetch failed");
    }

    const data = await res.json();
    if (!data?.plan || !data?.usage || !data?.profile) {
        throw new Error("Subscription response missing required fields");
    }
    return data as SubscriptionResponse;
}

export async function fetchCreditsEstimate(
    payload: {
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
    }
): Promise<CreditsEstimateResponse> {
    const baseUrl =
        process.env.NEXT_PUBLIC_API_BASE_URL ||
        process.env.NEXT_PUBLIC_API_URL ||
        "http://localhost:9000";
    const res = await fetch(`${baseUrl}/api/v1/credits/estimate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || "Credits estimate failed");
    }
    return (await res.json()) as CreditsEstimateResponse;
}

/**
 * Calculate solve cost based on mode and features used.
 */
export function calculateSolveCost(
    subscription: SubscriptionResponse,
    answerStyle: "quick" | "tutor",
    ocrUsed: boolean,
    voiceUsed: boolean
): number {
    const { multipliers } = subscription.plan;

    // Check for V1 schema
    if (multipliers.version === 1 && multipliers.credits) {
        const tier = answerStyle === "tutor" ? "standard" : "free";
        const tierConfig = multipliers.credits.solve[tier];

        if (voiceUsed) return tierConfig.voice;
        if (ocrUsed) return tierConfig.snap_image;
        return tierConfig.text;
    }

    // Legacy Fallback
    let cost = answerStyle === "tutor"
        ? (multipliers.text_detailed || 2)
        : (multipliers.text_concise || 1);

    if (ocrUsed) cost += (multipliers.ocr_add || 1);
    if (voiceUsed) cost += (multipliers.voice_add || 1);

    return cost;
}
