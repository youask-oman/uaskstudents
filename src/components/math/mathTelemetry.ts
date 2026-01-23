type MathTelemetryState = {
    typesetFailCount: number;
    malformedLatexCount: number;
    totalTypesetTimeMs: number;
    typesetCount: number;
    renderEngineUsed: string | null;
};

const state: MathTelemetryState = {
    typesetFailCount: 0,
    malformedLatexCount: 0,
    totalTypesetTimeMs: 0,
    typesetCount: 0,
    renderEngineUsed: null,
};

export const markTypesetFailure = (error?: unknown) => {
    state.typesetFailCount += 1;
    console.warn("[math] typeset failure", error);
};

export const markMalformedLatex = (latex: string) => {
    state.malformedLatexCount += 1;
    console.warn("[math] malformed latex", latex);
};

export const recordTypesetDuration = (ms: number) => {
    state.typesetCount += 1;
    state.totalTypesetTimeMs += ms;
};

export const setRenderEngineUsed = (engine: string) => {
    if (state.renderEngineUsed === engine) return;
    state.renderEngineUsed = engine;
    console.info(`[math] render engine: ${engine}`);
};

export const getMathTelemetrySnapshot = () => {
    const avg = state.typesetCount === 0 ? 0 : state.totalTypesetTimeMs / state.typesetCount;
    return {
        typeset_fail_count: state.typesetFailCount,
        malformed_latex_count: state.malformedLatexCount,
        avg_typeset_time_ms: Math.round(avg),
        render_engine_used: state.renderEngineUsed,
    };
};
