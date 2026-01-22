/**
 * Types and API client for subscription/tier-aware solve UX.
 */

export interface SubscriptionPlan {
    id: number;
    slug: string;
    display_name: string;
    credits_monthly: number;
    seats: number;
    multipliers: {
        text_concise: number;
        text_detailed: number;
        ocr_add: number;
        voice_add: number;
    };
    features: Record<string, any>;
}

export interface SubscriptionUsage {
    credits_used: number;
    credits_remaining: number;
    ocr_used: number;
    ocr_limit: number;
    voice_used: number;
    voice_limit: number;
}

export interface SubscriptionProfile {
    grade_level: string | null;
    region_country: string | null;
    region_state_province: string | null;
    display_name: string;
}

export interface SubscriptionResponse {
    plan: SubscriptionPlan;
    usage: SubscriptionUsage;
    profile: SubscriptionProfile;
    allow_detailed: boolean;
    allow_ocr: boolean;
    allow_voice: boolean;
}

// Default fallback for when API fails
export const DEFAULT_SUBSCRIPTION: SubscriptionResponse = {
    plan: {
        id: 0,
        slug: "free",
        display_name: "Free",
        credits_monthly: 50,
        seats: 1,
        multipliers: { text_concise: 1, text_detailed: 1000, ocr_add: 1, voice_add: 1 },
        features: {}
    },
    usage: {
        credits_used: 0,
        credits_remaining: 50,
        ocr_used: 0,
        ocr_limit: 3,
        voice_used: 0,
        voice_limit: 3
    },
    profile: {
        grade_level: null,
        region_country: null,
        region_state_province: null,
        display_name: "Guest"
    },
    allow_detailed: false,
    allow_ocr: true,
    allow_voice: true
};

/**
 * Fetch subscription details for tier-aware solve UX.
 */
export async function fetchSubscription(userId: string): Promise<SubscriptionResponse> {
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "";
    const res = await fetch(`${baseUrl}/api/v1/me/subscription?user_id=${userId}`);

    if (!res.ok) {
        console.warn("[Subscription] Failed to fetch, using defaults");
        return DEFAULT_SUBSCRIPTION;
    }

    return res.json();
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

    let cost = answerStyle === "tutor"
        ? multipliers.text_detailed
        : multipliers.text_concise;

    if (ocrUsed) cost += multipliers.ocr_add;
    if (voiceUsed) cost += multipliers.voice_add;

    return cost;
}
