export type SolveBatchMode = "free_minimal" | "final_only" | "standard_detailed" | "research_detailed";
export type SolveBatchTier = "FREE" | "STANDARD" | "RESEARCH";

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
    free_minimal: 10,
    final_only: 10,
    standard_detailed: 3,
    research_detailed: 1,
};

export function resolveSolveBatchMode(tier: string, requestedMode?: string): SolveBatchMode {
    const t = String(tier || "").trim().toUpperCase();
    if (t === "SHORT" || t === "FINAL" || t === "FINAL_ONLY") return "final_only";
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
    return "FREE";
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

export function mapSolveBatchErrorMessage(code?: string, maxAllowed?: number): string {
    if (code === "TOO_MANY_QUESTIONS") {
        const cap = typeof maxAllowed === "number" ? maxAllowed : 1;
        return `This mode supports up to ${cap} question(s). Reduce selection.`;
    }
    if (code === "PROVIDER_TIMEOUT" || code === "LLM_TIMEOUT" || code === "TIMEOUT") {
        return "Timed out. Try fewer questions or a lighter mode.";
    }
    if (code === "SCHEMA_INVALID") {
        return "Response formatting failed. Please retry.";
    }
    return "Solve failed. Please retry.";
}
