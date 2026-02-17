export type SolveBatchMode = "free_minimal" | "final_only" | "standard_detailed" | "research_detailed";
export type SolveBatchTier = "SHORT_STEPS" | "FINAL" | "STANDARD" | "RESEARCH";

export type SolveBatchQuestion = {
    question_id: string;
    text: string;
};

export type BuildSolveBatchPayloadInput = {
    selectedQuestions: Array<{ question_id?: string; text?: string } | SolveBatchQuestion>;
    mode: SolveBatchMode;
    tier: SolveBatchTier;
};

export const SOLVE_BATCH_CAPS: Record<SolveBatchMode, number> = {
    free_minimal: 5,
    final_only: 15,
    standard_detailed: 2,
    research_detailed: 1,
};

export function resolveSolveBatchMode(tier: string, requestedMode?: string): SolveBatchMode {
    const t = String(tier || "").trim().toUpperCase();
    if (t === "FINAL" || t === "SHORT" || t === "FINAL_ONLY") return "final_only";
    if (t === "RESEARCH") return "research_detailed";
    if (t === "STANDARD") return "standard_detailed";

    const mode = String(requestedMode || "").trim().toLowerCase();
    if (mode === "detailed") return "standard_detailed";
    return "free_minimal";
}

export function resolveSolveBatchTier(tier: string): SolveBatchTier {
    const t = String(tier || "").trim().toUpperCase();
    if (t === "RESEARCH") return "RESEARCH";
    if (t === "STANDARD") return "STANDARD";
    if (t === "FINAL" || t === "SHORT") return "FINAL";
    return "SHORT_STEPS";
}

export function getSolveBatchCap(mode: SolveBatchMode): number {
    return SOLVE_BATCH_CAPS[mode];
}

export function buildSolveBatchPayload(input: BuildSolveBatchPayloadInput): {
    requested_mode: SolveBatchMode;
    tier: SolveBatchTier;
    questions: SolveBatchQuestion[];
} {
    const questions = input.selectedQuestions
        .map((q) => ({
            question_id: String((q as { question_id?: string }).question_id || "").trim(),
            text: String((q as { text?: string }).text || "").trim(),
        }))
        .filter((q) => q.question_id && q.text);

    return {
        requested_mode: input.mode,
        tier: input.tier,
        questions,
    };
}

export function mapSolveBatchErrorMessage(
    code?: string,
    maxAllowed?: number,
    details?: Record<string, unknown> | null
): string {
    if (code === "TOO_MANY_QUESTIONS") {
        const cap = typeof maxAllowed === "number" ? maxAllowed : 1;
        return `This mode supports up to ${cap} question(s). Reduce selection.`;
    }
    if (code === "PROVIDER_TIMEOUT" || code === "LLM_TIMEOUT" || code === "TIMEOUT") {
        return "Provider timeout. You were NOT charged. Retry with a new request.";
    }
    if (code === "already_processed") {
        return "This request was already processed; no additional charge was applied.";
    }
    if (code === "insufficient_credits") {
        return "Insufficient credits. Please top up and retry.";
    }
    if (code === "SCHEMA_INVALID") {
        return "Response formatting failed. Please retry.";
    }
    if (code === "final_local_only_unsatisfied") {
        const reason = String(details?.reason || "").trim();
        const qid = String(details?.question_id || "").trim();
        const solved = Number(details?.items_solved_locally ?? NaN);
        const total = Number(details?.items_total ?? NaN);
        const parts: string[] = ["FINAL local-only mode blocked fallback."];
        if (reason) parts.push(`reason=${reason}`);
        if (qid) parts.push(`question=${qid}`);
        if (Number.isFinite(solved) && Number.isFinite(total)) parts.push(`solved=${solved}/${total}`);
        return parts.join(" ");
    }
    if (code === "sympy_numpy_gate_failed") {
        const qid = String(details?.question_id || "").trim();
        const err = String(details?.error || "").trim();
        return `SymPy/NumPy gate failed${qid ? ` at ${qid}` : ""}${err ? `: ${err}` : "."}`;
    }
    if (code === "openai_request_failed") {
        const providerDetails = details?.provider_details ? JSON.stringify(details.provider_details) : "";
        return `OpenAI request failed${providerDetails ? `: ${providerDetails}` : "."}`;
    }
    return "Solve failed. Please retry.";
}
