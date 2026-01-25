export interface TokenPolicy {
    text: {
        input_max: number;
        input_max_chars: number;
        output_max: {
            minimal: { solve: number; study: number };
            detailed: { solve: number; study: number };
        };
    };
    request: {
        system_and_schema_budget: number;
        expected_output_budget: number;
    };
    ocr_image: {
        extract_max: number;
        input_max: number;
        input_overhead: number;
    };
    ocr_pdf: {
        extract_max: number;
        input_max: number;
        input_overhead: number;
    };
    voice: {
        input_max: number;
        input_overhead: number;
    };
}

interface TokenPolicyResponse {
    ok: boolean;
    policy: TokenPolicy;
}

export async function fetchTokenPolicy(): Promise<TokenPolicy> {
    const res = await fetch("/api/v1/config/token-policy", { cache: "no-store" });
    if (!res.ok) {
        const message = await res.text();
        throw new Error(message || "Failed to load token policy");
    }
    const data = (await res.json()) as TokenPolicyResponse;
    if (!data?.ok || !data.policy) {
        throw new Error("Token policy unavailable");
    }
    return data.policy;
}
