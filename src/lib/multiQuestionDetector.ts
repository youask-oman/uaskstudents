/**
 * Multi-Question Detector
 *
 * Detects when user input contains multiple questions and provides
 * auto-split functionality to separate them.
 */

import {
    CONNECTOR_PATTERN,
    LIST_MARKER_PATTERNS,
    MATH_HEAVY_THRESHOLDS,
    MIN_QUESTION_MARKS_FOR_WARNING,
    MULTI_QUESTION_PATTERNS,
} from "./multiQuestionConfig";

export interface MultiQuestionResult {
    isMultiple: boolean;
    confidence: "high" | "medium" | "low";
    questionMarks: number;
    matchedPatterns: string[];
    suggestedSplits: string[];
}

interface MathHeavinessStats {
    latexCommands: number;
    operators: number;
    digits: number;
    parentheses: number;
    equationLines: number;
}

interface MathHeavinessResult {
    isMathHeavy: boolean;
    stats: MathHeavinessStats;
}

interface SplitCandidate {
    source: "numbered" | "taskVerb" | "questionMark" | "blankLine";
    parts: string[];
}

const TASK_VERB_RE =
    /\b(solve|find|determine|compute|calculate|evaluate|derive|state|report|identify|list|describe|classify|discuss|show|use|convert|rewrite|express|factor|simplify|expand|transform|verify|check|confirm|match|justify|prove|format|arrange|order|standardize|interpret)\b/i;

const VERB_CLASS_MAP: Record<string, "SOLVE" | "TRANSFORM" | "VERIFY" | "FORMAT" | "OTHER"> = {
    solve: "SOLVE",
    find: "SOLVE",
    determine: "SOLVE",
    compute: "SOLVE",
    calculate: "SOLVE",
    evaluate: "SOLVE",
    derive: "SOLVE",
    state: "SOLVE",
    report: "SOLVE",
    identify: "SOLVE",
    list: "SOLVE",
    describe: "SOLVE",
    classify: "SOLVE",
    discuss: "SOLVE",
    use: "SOLVE",
    rewrite: "TRANSFORM",
    express: "TRANSFORM",
    factor: "TRANSFORM",
    simplify: "TRANSFORM",
    expand: "TRANSFORM",
    transform: "TRANSFORM",
    convert: "TRANSFORM",
    show: "VERIFY",
    verify: "VERIFY",
    check: "VERIFY",
    confirm: "VERIFY",
    match: "VERIFY",
    justify: "VERIFY",
    prove: "VERIFY",
    format: "FORMAT",
    arrange: "FORMAT",
    order: "FORMAT",
    standardize: "FORMAT",
    interpret: "FORMAT",
};

const TASK_START_LINE_RE =
    /^\s*(?:[-*•]\s+|Q\d{1,3}[.:)\s-]*|\d{1,3}[.)]\s+|\([a-z]\)\s+|[a-z]\)\s+|(step|part)\s+(\d+|[a-z]+|\([ivx]+\))[:.)\s-]+)/i;

const STRIP_TASK_PREFIX_RE =
    /^\s*(?:[-*•]\s+|Q\d{1,3}[.:)\s-]*|\d{1,3}[.)]\s+|\([a-z]\)\s+|[a-z]\)\s+|(step|part)\s+(\d+|[a-z]+|\([ivx]+\))[:.)\s-]+)/i;

const EQUATION_LINE_RE = /[A-Za-z0-9)\]]\s*=\s*[A-Za-z0-9(\\]/;
const LATEX_PATTERN = /\\[a-zA-Z]+/g;
const OPERATOR_PATTERN = /[=+\-*/<>^_]/g;
const DIGIT_PATTERN = /\d/g;
const PAREN_PATTERN = /[()[\]{}]/g;
const QUESTION_HEADER_RE = /^\s*(?:question\b(?:\s*\d+)?(?:\s*\([^)\n]+\))?|problem\b|q\d{1,3}\b)/i;

export function detectMultiQuestion(text: string): MultiQuestionResult {
    const normalized = normalizeNewlines(text).trim();
    const source = sanitizeForDetection(normalized).trim();
    const matchedPatterns: string[] = [];
    const suggestedSplits = autoSplitQuestions(normalized);
    const questionMarks = (source.match(/\?/g) || []).length;
    const taskLineCount = countTaskLines(source);
    const listMarkerCount = countListMarkers(source);
    const connectorCount = countMatches(CONNECTOR_PATTERN, source);
    const equationBlocks = countEquationBlocks(source);

    let score = 0;

    if (listMarkerCount >= 2) {
        score += 3;
        matchedPatterns.push(`list markers=${listMarkerCount}`);
    }
    if (suggestedSplits.length >= 2) {
        score += 2;
        matchedPatterns.push(`auto-split produced ${suggestedSplits.length} tasks`);
    }
    if (questionMarks >= MIN_QUESTION_MARKS_FOR_WARNING) {
        score += 2;
        matchedPatterns.push(`${questionMarks} question marks`);
    }
    if (taskLineCount >= 2) {
        score += 2;
        matchedPatterns.push(`task lines=${taskLineCount}`);
    }
    if (equationBlocks >= 2) {
        score += 2;
        matchedPatterns.push(`math-heavy equation blocks=${equationBlocks}`);
    }
    if (connectorCount > 0 && score > 0) {
        score += 1;
        matchedPatterns.push(`connector words=${connectorCount}`);
    }

    let confidence: "high" | "medium" | "low" = "low";
    if (score >= 5) confidence = "high";
    else if (score >= 3) confidence = "medium";

    return {
        isMultiple: score >= 3 || suggestedSplits.length >= 2,
        confidence,
        questionMarks,
        matchedPatterns,
        suggestedSplits: suggestedSplits.length >= 2 ? suggestedSplits : [],
    };
}

export function autoSplitQuestions(text: string): string[] {
    const rawSource = normalizeNewlines(text).trim();
    if (!rawSource) return [text];
    const signalSource = sanitizeForDetection(rawSource).trim();

    const candidates: SplitCandidate[] = [
        // Keep raw text here so question-level splits preserve full MCQ choices/options.
        { source: "numbered", parts: splitByNumberedPatterns(rawSource) },
        // Use sanitized text for heuristic splitters to avoid false splits inside Choices blocks.
        { source: "taskVerb", parts: splitByTaskVerbHeuristics(signalSource) },
        { source: "questionMark", parts: splitByQuestionMarks(signalSource) },
        { source: "blankLine", parts: splitByBlankLines(signalSource) },
    ];

    const valid = candidates.filter((c) => c.parts.length >= 2);
    if (valid.length === 0) return [text];

    const priority: Record<SplitCandidate["source"], number> = {
        numbered: 0,
        taskVerb: 1,
        questionMark: 2,
        blankLine: 3,
    };

    valid.sort((a, b) => {
        if (b.parts.length !== a.parts.length) return b.parts.length - a.parts.length;
        return priority[a.source] - priority[b.source];
    });

    const winner = valid[0];
    if (winner.source === "numbered") {
        return cleanSplits(winner.parts);
    }
    return stripSharedPreamble(winner.parts);
}

export function extractSharedContext(text: string): string {
    const src = normalizeNewlines(text).trim();
    if (!src) return "";
    const questionHeaderCount = src
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => QUESTION_HEADER_RE.test(line)).length;
    if (questionHeaderCount >= 2) return "";

    const lineSegments = buildLineSegments(src);
    if (lineSegments.length >= 2) {
        const firstTaskIdx = lineSegments.findIndex((seg) => TASK_VERB_RE.test(seg));
        if (firstTaskIdx > 0) {
            return lineSegments.slice(0, firstTaskIdx).join(" ").trim();
        }
    }

    const sentenceSegments = src.split(/(?<=[.?!;])\s+/).map((s) => s.trim()).filter(Boolean);
    if (sentenceSegments.length < 2) return "";
    const firstTaskIdx = sentenceSegments.findIndex((seg) => TASK_VERB_RE.test(seg));
    if (firstTaskIdx <= 0) return "";
    return sentenceSegments.slice(0, firstTaskIdx).join(" ").trim();
}

export function analyzeMathHeaviness(text: string): MathHeavinessResult {
    const source = normalizeNewlines(text);
    const stats: MathHeavinessStats = {
        latexCommands: countMatches(LATEX_PATTERN, source),
        operators: countMatches(OPERATOR_PATTERN, source),
        digits: countMatches(DIGIT_PATTERN, source),
        parentheses: countMatches(PAREN_PATTERN, source),
        equationLines: source
            .split("\n")
            .map((line) => line.trim())
            .filter((line) => line.length > 0 && EQUATION_LINE_RE.test(line)).length,
    };

    let conditionsMet = 0;
    if (stats.latexCommands >= MATH_HEAVY_THRESHOLDS.latexCommands) conditionsMet += 1;
    if (stats.operators >= MATH_HEAVY_THRESHOLDS.operators) conditionsMet += 1;
    if (stats.digits >= MATH_HEAVY_THRESHOLDS.digits) conditionsMet += 1;
    if (stats.parentheses >= MATH_HEAVY_THRESHOLDS.parentheses) conditionsMet += 1;
    if (stats.equationLines >= MATH_HEAVY_THRESHOLDS.equationLines) conditionsMet += 1;

    return {
        isMathHeavy: conditionsMet >= 2,
        stats,
    };
}

function countEquationBlocks(text: string): number {
    const blocks = text.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
    if (blocks.length < 2) return 0;

    const math = analyzeMathHeaviness(text);
    if (!math.isMathHeavy) return 0;

    const equationBlocks = blocks.filter((block) =>
        block
            .split("\n")
            .map((line) => line.trim())
            .some((line) => EQUATION_LINE_RE.test(line)),
    );
    return equationBlocks.length;
}

function splitByNumberedPatterns(text: string): string[] {
    const normalized = normalizeNewlines(text);
    const hasChoicesSection = /(^|\n)\s*choices\b/i.test(normalized);

    const isQuestionHeaderLike = (prefix: string): boolean => {
        const p = (prefix || "").trim().toLowerCase();
        if (!p) return false;
        return (
            /\bquestion\s*\d+\b/.test(p) ||
            /\bq\d+\b/.test(p) ||
            /\bmultiple[-\s]*choice\b/.test(p) ||
            /\bfinal answer\b/.test(p) ||
            /^choices\b/.test(p)
        );
    };

    const splitByLineMarkers = (source: string, marker: RegExp, markerStrip: RegExp): string[] => {
        const matches = [...source.matchAll(marker)];
        if (matches.length < 2) return [];

        const firstIdx = matches[0].index ?? 0;
        const prefix = source.slice(0, firstIdx).trim();
        const parts: string[] = [];

        for (let i = 0; i < matches.length; i += 1) {
            const start = matches[i].index ?? 0;
            const end = i + 1 < matches.length ? (matches[i + 1].index ?? source.length) : source.length;
            const raw = source.slice(start, end).trim();
            const cleaned = raw.replace(markerStrip, "").trim();
            if (!cleaned) continue;

            let finalPart = cleaned;
            if (
                prefix &&
                !isQuestionHeaderLike(prefix) &&
                !cleaned.toLowerCase().includes(prefix.toLowerCase())
            ) {
                finalPart = `${prefix}\n\n${cleaned}`;
            }
            parts.push(finalPart);
        }
        return cleanSplits(parts);
    };

    const qSplit = splitByLineMarkers(
        normalized,
        /^\s*Q\d{1,3}[.:)\s-]*/gim,
        /^\s*Q\d{1,3}[.:)\s-]*/i,
    );
    if (qSplit.length >= 2) return qSplit;

    const questionHeaderSplit = splitByLineMarkers(
        normalized,
        /^\s*question\b(?:\s*\d+)?(?:\s*\([^)\n]+\))?[:.)\s-]*/gim,
        /^\s*question\b(?:\s*\d+)?(?:\s*\([^)\n]+\))?[:.)\s-]*/i,
    );
    if (questionHeaderSplit.length >= 2) return questionHeaderSplit;

    const numericSplit = splitByLineMarkers(
        normalized,
        /^\s*\d{1,3}[.)]\s+/gm,
        /^\s*\d{1,3}[.)]\s+/,
    );
    if (numericSplit.length >= 2) return numericSplit;

    const withInlineBreaks = normalized.replace(/([.?!:;])\s+(\d{1,3}[.)]\s+)/g, "$1\n$2");
    const numericInlineSplit = splitByLineMarkers(
        withInlineBreaks,
        /^\s*\d{1,3}[.)]\s+/gm,
        /^\s*\d{1,3}[.)]\s+/,
    );
    if (numericInlineSplit.length >= 2) return numericInlineSplit;

    if (!hasChoicesSection) {
        const parenLetterSplit = splitByLineMarkers(
            normalized,
            /^\s*\([a-z]\)\s+/gim,
            /^\s*\([a-z]\)\s+/i,
        );
        if (parenLetterSplit.length >= 2) return parenLetterSplit;

        const letterSplit = splitByLineMarkers(
            normalized,
            /^\s*[a-z]\)\s+/gim,
            /^\s*[a-z]\)\s+/i,
        );
        if (letterSplit.length >= 2) return letterSplit;
    }

    const stepPartSplit = splitByLineMarkers(
        normalized,
        /^\s*(?:step|part)\s+(?:\d+|[a-z]+|\([ivx]+\))[:.)\s-]+/gim,
        /^\s*(?:step|part)\s+(?:\d+|[a-z]+|\([ivx]+\))[:.)\s-]+/i,
    );
    if (stepPartSplit.length >= 2) return stepPartSplit;

    return [];
}

function splitByTaskVerbHeuristics(text: string): string[] {
    const src = normalizeNewlines(text).trim();
    if (!src) return [];

    const lineSegments = buildLineSegments(src);
    const punctuationSegments = src.split(/(?<=[.?!;])\s+/).map((s) => s.trim()).filter(Boolean);
    const segments = lineSegments.length >= 2 ? lineSegments : punctuationSegments;
    if (segments.length < 2) return [];

    const outputs: string[] = [];
    const seen = new Set<string>();

    for (const rawSegment of segments) {
        const segment = rawSegment.replace(STRIP_TASK_PREFIX_RE, "").trim();
        if (!segment) continue;
        const verbMatch = segment.match(TASK_VERB_RE);
        if (!verbMatch) continue;

        const verb = verbMatch[1]?.toLowerCase() || "";
        const verbClass = VERB_CLASS_MAP[verb] || "OTHER";
        const scopeKey = extractScopeKey(segment);
        const dedupeKey = `${verbClass}|${scopeKey}|${normalizeForDedupe(segment)}`;
        if (seen.has(dedupeKey)) continue;
        seen.add(dedupeKey);
        outputs.push(segment);
    }

    return cleanSplits(mergeFollowUpJustifications(outputs));
}

function splitByQuestionMarks(text: string): string[] {
    const parts = text.split(/\?\s*/).map((p) => p.trim()).filter((p) => p.length > 5);
    return parts.map((p) => (p.endsWith("?") ? p : `${p}?`));
}

function splitByBlankLines(text: string): string[] {
    const rawParts = text.split(/\n\s*\n/).map((p) => p.trim()).filter((p) => p.length > 0);
    if (rawParts.length <= 1) return rawParts.filter((p) => p.length > 5);

    const merged: string[] = [];
    for (const part of rawParts) {
        if (isChoicesOnlyBlock(part) && merged.length > 0) {
            merged[merged.length - 1] = `${merged[merged.length - 1]}\n\n${part}`.trim();
        } else {
            merged.push(part);
        }
    }
    return merged.filter((p) => p.length > 5);
}

function isChoicesOnlyBlock(block: string): boolean {
    const lines = String(block || "")
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
    if (lines.length === 0) return false;
    return lines.every((line) =>
        /^choices\b/i.test(line) ||
        /^\(?[a-e]\)?[).:\-]?\s+/.test(line),
    );
}

function buildLineSegments(text: string): string[] {
    const lines = text.split("\n").map((line) => line.trim()).filter((line) => line.length > 0);
    if (lines.length === 0) return [];

    const segments: string[] = [];
    let current = "";

    for (const line of lines) {
        const isTaskStart = TASK_START_LINE_RE.test(line);
        const isQuestionStart = QUESTION_HEADER_RE.test(line);
        const isVerbStart = startsWithTaskVerb(line);
        const shouldStartNew = isTaskStart || isQuestionStart || (isVerbStart && current.trim().length > 0);

        if (shouldStartNew) {
            if (current.trim()) segments.push(current.trim());
            current = line;
            continue;
        }

        if (!current) {
            current = line;
        } else {
            current = `${current} ${line}`;
        }
    }

    if (current.trim()) segments.push(current.trim());
    return segments;
}

function startsWithTaskVerb(line: string): boolean {
    const cleaned = String(line || "").replace(STRIP_TASK_PREFIX_RE, "").trim();
    const m = cleaned.match(/^([a-z]+)/i);
    if (!m?.[1]) return false;
    return TASK_VERB_RE.test(m[1]);
}

function mergeFollowUpJustifications(parts: string[]): string[] {
    if (parts.length < 2) return parts;
    const merged: string[] = [];
    for (const raw of parts) {
        const current = String(raw || "").trim();
        if (!current) continue;
        const isFollowUp =
            /^(justify|explain|show why)\b/i.test(current) ||
            /^if\s+(yes|no)\b/i.test(current);
        if (isFollowUp && merged.length > 0) {
            merged[merged.length - 1] = `${merged[merged.length - 1]} ${current}`.trim();
            continue;
        }
        merged.push(current);
    }
    return merged;
}

function normalizeForDedupe(segment: string): string {
    return segment
        .replace(STRIP_TASK_PREFIX_RE, "")
        .toLowerCase()
        .replace(/\s+/g, " ")
        .replace(/[^\w\s\\[\](){}^_+=\-*/<>|.,]/g, "")
        .trim();
}

function extractScopeKey(segment: string): string {
    const lower = segment.toLowerCase();
    if (/\b[a-z]\s*in\s*\[/.test(lower)) return "domain_restricted";
    if (lower.includes("[0,2") && (lower.includes("pi") || lower.includes("π"))) return "domain_restricted";
    return "default";
}

function countTaskLines(text: string): number {
    const segments = buildLineSegments(text);
    return segments.filter((seg) => TASK_VERB_RE.test(seg)).length;
}

function countListMarkers(text: string): number {
    let total = 0;
    for (const pattern of LIST_MARKER_PATTERNS) {
        total += countMatches(pattern, text);
    }
    return total;
}

function countMatches(pattern: RegExp, text: string): number {
    pattern.lastIndex = 0;
    return (text.match(pattern) || []).length;
}

function cleanSplits(parts: string[]): string[] {
    return parts
        .map((p) => p.trim())
        .filter((p) => p.length > 5)
        .filter((p) => !/^[1-9a-e]$/i.test(p));
}

function stripSharedPreamble(parts: string[]): string[] {
    if (parts.length < 2) return cleanSplits(parts);
    const first = String(parts[0] || "").trim();
    const m = first.match(/^(.+?[.?!])\s+/);
    if (!m?.[1]) return cleanSplits(parts);
    const preamble = m[1].trim();
    const prefixed = parts.filter((p) =>
        String(p || "")
            .trim()
            .toLowerCase()
            .startsWith(`${preamble} `.toLowerCase()),
    );
    if (prefixed.length < 2) return cleanSplits(parts);
    const stripped = parts.map((p) => {
        const t = String(p || "").trim();
        if (t.toLowerCase().startsWith(`${preamble} `.toLowerCase())) {
            return t.slice(preamble.length).trim();
        }
        return t;
    });
    return cleanSplits(stripped);
}

function normalizeNewlines(text: string): string {
    return String(text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
}

function sanitizeForDetection(text: string): string {
    const lines = normalizeNewlines(text).split("\n");
    const kept: string[] = [];
    let inChoices = false;

    for (const line of lines) {
        const trimmed = line.trim();
        if (/^choices\s*$/i.test(trimmed)) {
            inChoices = true;
            continue;
        }

        if (inChoices) {
            // Skip all option lines after "Choices", even when choice markers are malformed/stripped.
            // Exit only when we detect a clear new problem/question header.
            if (QUESTION_HEADER_RE.test(trimmed)) {
                inChoices = false;
            } else {
                continue;
            }
        }

        kept.push(line);
    }

    return kept.join("\n");
}

export function shouldShowSplitUI(text: string): boolean {
    const result = detectMultiQuestion(text);
    return result.confidence === "high" || (result.confidence === "medium" && result.suggestedSplits.length >= 3);
}

// Backward-compatible export for tooling that imports this constant from the detector module.
export { MULTI_QUESTION_PATTERNS };
