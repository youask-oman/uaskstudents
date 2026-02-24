"use strict";
/* eslint-disable @typescript-eslint/no-require-imports */
/**
 * Multi-Question Detector
 *
 * Detects when user input contains multiple questions and provides
 * auto-split functionality to separate them.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.detectMultiQuestion = detectMultiQuestion;
exports.autoSplitQuestions = autoSplitQuestions;
exports.extractSharedContext = extractSharedContext;
exports.shouldShowSplitUI = shouldShowSplitUI;
const tokenBudget_1 = require("./tokenBudget");
// ============================================================================
// MAIN DETECTION FUNCTION
// ============================================================================
/**
 * Detect if input contains multiple questions
 *
 * Flags input as multi-question if:
 * - 2+ question marks
 * - Patterns like Q1, Q2, 1), (a), "also find", etc.
 * - Multiple blank-line-separated blocks with equations
 *
 * @param text - Input text to analyze
 * @returns MultiQuestionResult with detection details
 */
function detectMultiQuestion(text) {
    const matchedPatterns = [];
    // Count question marks
    const questionMarks = (text.match(/\?/g) || []).length;
    if (questionMarks >= tokenBudget_1.MIN_QUESTION_MARKS_FOR_WARNING) {
        matchedPatterns.push(`${questionMarks} question marks`);
    }
    // Check each pattern
    // Check each pattern
    for (const pattern of tokenBudget_1.MULTI_QUESTION_PATTERNS) {
        // Reset lastIndex for global patterns
        pattern.lastIndex = 0;
        const matches = text.match(pattern);
        if (!matches || matches.length === 0)
            continue;
        // Distinguish between connectors (also/then/next) and list markers (1), Q1, etc.)
        // Connectors imply multiplicity even if appearing once.
        // List markers must appear at least twice to imply a list.
        const firstMatch = matches[0].trim().toLowerCase();
        const isConnector = firstMatch.startsWith('also') ||
            firstMatch.startsWith('then') ||
            firstMatch.startsWith('next');
        if (isConnector) {
            matchedPatterns.push(`Pattern: ${matches[0]}`);
        }
        else if (matches.length >= 2) {
            matchedPatterns.push(`${matches.length}x pattern '${matches[0]}'`);
        }
    }
    // Check for multiple equation blocks separated by blank lines
    const blocks = text.split(/\n\s*\n/).filter(b => b.trim().length > 0);
    const equationBlocks = blocks.filter(block => /[=]/.test(block));
    if (equationBlocks.length >= 2) {
        matchedPatterns.push(`${equationBlocks.length} equation blocks`);
    }
    // Run full splitter as an additional detection signal.
    // This catches paragraph-style multi-task prompts before the user clicks solve.
    const suggestedSplits = autoSplitQuestions(text);
    if (suggestedSplits.length >= 2) {
        matchedPatterns.push(`auto-split produced ${suggestedSplits.length} tasks`);
    }
    // Determine confidence
    let confidence = 'low';
    if (matchedPatterns.length >= 3 || suggestedSplits.length >= 4) {
        confidence = 'high';
    }
    else if (matchedPatterns.length >= 1) {
        confidence = 'medium';
    }
    return {
        isMultiple: matchedPatterns.length >= 1 || suggestedSplits.length >= 2,
        confidence,
        questionMarks,
        matchedPatterns,
        suggestedSplits: suggestedSplits.length >= 2 ? suggestedSplits : [],
    };
}
// ============================================================================
// AUTO-SPLIT FUNCTION
// ============================================================================
/**
 * Attempt to split multiple questions into separate parts
 *
 * Split strategies (in order of preference):
 * 1. By numbered patterns: Q1, Q2 or 1), 2) or (a), (b)
 * 2. By question mark boundaries
 * 3. By blank-line-separated blocks
 *
 * @param text - Input text to split
 * @returns Array of sub-questions
 */
function autoSplitQuestions(text) {
    let selected = [];
    // Try numbered patterns first
    const numberedSplit = splitByNumberedPatterns(text);
    if (numberedSplit.length >= 2) {
        selected = numberedSplit;
    }
    if (selected.length < 2) {
        // Try question mark boundaries
        const questionSplit = splitByQuestionMarks(text);
        if (questionSplit.length >= 2) {
            selected = questionSplit;
        }
    }
    if (selected.length < 2) {
        // Try blank-line blocks
        const blockSplit = splitByBlankLines(text);
        if (blockSplit.length >= 2) {
            selected = blockSplit;
        }
    }
    if (selected.length < 2) {
        // Try paragraph task segmentation (Step A/B/C heuristic)
        const taskSplit = splitByTaskVerbHeuristics(text);
        if (taskSplit.length >= 2) {
            selected = taskSplit;
        }
    }
    if (selected.length >= 2) {
        return stripSharedPreamble(selected);
    }
    // No good split found
    return [text];
}
/**
 * Extract shared context/preamble from a multi-task prompt.
 * Example:
 * "Let ... . Compute A. Compute B." -> "Let ... ."
 */
function extractSharedContext(text) {
    const src = String(text || "").replace(/\r/g, "").trim();
    if (!src)
        return "";
    const segments = src.split(/(?<=[.?!;])\s+/).map(s => s.trim()).filter(Boolean);
    if (segments.length < 2)
        return "";
    let firstTaskIdx = -1;
    for (let i = 0; i < segments.length; i += 1) {
        if (TASK_VERB_RE.test(segments[i])) {
            firstTaskIdx = i;
            break;
        }
    }
    if (firstTaskIdx <= 0)
        return "";
    return segments.slice(0, firstTaskIdx).join(" ").trim();
}
/**
 * Split by numbered patterns (Q1, 1), (a), etc.)
 */
function splitByNumberedPatterns(text) {
    const normalized = text.replace(/\r\n/g, "\n");
    const splitByLineMarkers = (source, marker) => {
        const matches = [...source.matchAll(marker)];
        if (matches.length < 2)
            return [];
        const parts = [];
        for (let i = 0; i < matches.length; i += 1) {
            const start = matches[i].index ?? 0;
            const end = i + 1 < matches.length ? (matches[i + 1].index ?? source.length) : source.length;
            const raw = source.slice(start, end).trim();
            const cleaned = raw
                .replace(/^\s*Q\d{1,3}[.:)\s-]*/i, "")
                .replace(/^\s*\d{1,3}[.)]\s*/, "")
                .trim();
            if (cleaned.length > 0)
                parts.push(cleaned);
        }
        return cleanSplits(parts);
    };
    // Try Q1/Q2... at start of lines.
    const qLineSplit = splitByLineMarkers(normalized, /^\s*Q\d{1,3}[.:)\s-]*/gim);
    if (qLineSplit.length >= 2)
        return qLineSplit;
    // Try numeric 1), 2), ... 10), 11), ...
    const numericLineSplit = splitByLineMarkers(normalized, /^\s*\d{1,3}[.)]\s+/gm);
    if (numericLineSplit.length >= 2)
        return numericLineSplit;
    // Handle inline numbering in the same physical line: "... 10) ... 11) ..."
    const withInlineBreaks = normalized.replace(/([.?!:;])\s+(\d{1,3}[.)]\s+)/g, "$1\n$2");
    const numericInlineSplit = splitByLineMarkers(withInlineBreaks, /^\s*\d{1,3}[.)]\s+/gm);
    if (numericInlineSplit.length >= 2)
        return numericInlineSplit;
    // Try (a), (b), ...
    const letterPattern = /^\s*\([a-e]\)\s*/gm;
    const letterParts = withInlineBreaks.split(letterPattern).filter(p => p.trim().length > 1);
    if (letterParts.length >= 2)
        return cleanSplits(letterParts);
    return [];
}
/**
 * Split by question marks
 */
function splitByQuestionMarks(text) {
    // Split on ? but keep context
    const parts = text.split(/\?\s*/).filter(p => p.trim().length > 5);
    return parts.map(p => p.trim() + (p.endsWith('?') ? '' : '?'));
}
/**
 * Split by blank lines
 */
function splitByBlankLines(text) {
    return text.split(/\n\s*\n/).filter(p => p.trim().length > 5).map(p => p.trim());
}
/**
 * Clean up splits: remove empty, trim, filter too-short
 */
function cleanSplits(parts) {
    return parts
        .map(p => p.trim())
        .filter(p => p.length > 5) // Minimum meaningful length
        .filter(p => !/^[1-9a-e]$/i.test(p)); // Filter out lone numbers/letters
}
function stripSharedPreamble(parts) {
    if (parts.length < 2)
        return cleanSplits(parts);
    const first = String(parts[0] || "").trim();
    const m = first.match(/^(.+?[.?!])\s+/);
    if (!m?.[1])
        return cleanSplits(parts);
    const preamble = m[1].trim();
    const prefixed = parts.filter((p) => String(p || "").trim().toLowerCase().startsWith((preamble + " ").toLowerCase()));
    if (prefixed.length < 2)
        return cleanSplits(parts);
    const stripped = parts.map((p) => {
        const t = String(p || "").trim();
        if (t.toLowerCase().startsWith((preamble + " ").toLowerCase())) {
            return t.slice(preamble.length).trim();
        }
        return t;
    });
    return cleanSplits(stripped);
}
// ============================================================================
// TASK-VERB HEURISTIC (Step A/B/C)
// ============================================================================
const TASK_VERB_RE = /\b(solve|find|determine|compute|calculate|evaluate|derive|state|report|identify|list|rewrite|express|factor|simplify|expand|transform|verify|check|confirm|justify|prove|format|arrange|order|standardize|interpret)\b/i;
const VERB_CLASS_MAP = {
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
    rewrite: "TRANSFORM",
    express: "TRANSFORM",
    factor: "TRANSFORM",
    simplify: "TRANSFORM",
    expand: "TRANSFORM",
    transform: "TRANSFORM",
    verify: "VERIFY",
    check: "VERIFY",
    confirm: "VERIFY",
    justify: "VERIFY",
    prove: "VERIFY",
    format: "FORMAT",
    arrange: "FORMAT",
    order: "FORMAT",
    standardize: "FORMAT",
    interpret: "FORMAT",
};
function splitByTaskVerbHeuristics(text) {
    const src = String(text || "").replace(/\r/g, "").trim();
    if (!src)
        return [];
    const segments = src.split(/(?<=[.?!;])\s+/).map(s => s.trim()).filter(Boolean);
    if (segments.length < 2)
        return [];
    const preamble = segments[0];
    const candidates = segments.slice(1);
    const outputs = [];
    const seen = new Set();
    for (const seg of candidates) {
        const verbMatch = seg.match(TASK_VERB_RE);
        if (!verbMatch)
            continue;
        const verb = verbMatch[1]?.toLowerCase() || "";
        const verbClass = VERB_CLASS_MAP[verb] || "OTHER";
        const objectKey = extractObjectKey(seg);
        const scopeKey = extractScopeKey(seg);
        const intentKey = extractIntentKey(seg);
        const segmentKey = normalizeSegmentForDedupe(seg);
        const dedupeKey = `${verbClass}|${objectKey}|${scopeKey}|${intentKey}|${segmentKey}`;
        if (seen.has(dedupeKey))
            continue;
        seen.add(dedupeKey);
        // Keep each split concise; do not repeat the shared preamble on every task.
        // The caller can render preamble/context separately if needed.
        const taskOnly = seg.trim();
        if (taskOnly.length > 0 && taskOnly.toLowerCase() !== preamble.toLowerCase()) {
            outputs.push(taskOnly);
        }
    }
    return cleanSplits(outputs);
}
function extractObjectKey(segment) {
    const s = String(segment || "");
    const lower = s.toLowerCase();
    // High-signal probability/statistics targets first
    const corrMatch = s.match(/\bCorr\s*\(([^)]+)\)/i);
    if (corrMatch?.[1])
        return `corr(${corrMatch[1].replace(/\s+/g, "")})`;
    const covMatch = s.match(/\bCov\s*\(([^)]+)\)/i);
    if (covMatch?.[1])
        return `cov(${covMatch[1].replace(/\s+/g, "")})`;
    const condDensityMatch = s.match(/\bconditional\s+density\s+([^\.,;]+)/i);
    if (condDensityMatch?.[1])
        return `conditional_density:${normalizeObjectToken(condDensityMatch[1])}`;
    const marginalDensityMatch = s.match(/\bmarginal\s+density\s+([^\.,;]+)/i);
    if (marginalDensityMatch?.[1])
        return `marginal_density:${normalizeObjectToken(marginalDensityMatch[1])}`;
    const expMatch = s.match(/\bE\[[^\]]+\]/i);
    if (expMatch?.[0])
        return normalizeObjectToken(expMatch[0]);
    const probMatch = s.match(/\bP\s*\([^)]+\)/i);
    if (probMatch?.[0])
        return normalizeObjectToken(probMatch[0]);
    if (lower.includes("valid joint density") || lower.includes("integrating over its support")) {
        return "joint_density_validity";
    }
    const forVar = s.match(/\bfor\s+([a-zA-Z][a-zA-Z0-9_]*)\b/);
    if (forVar?.[1])
        return forVar[1].toLowerCase();
    if (lower.includes("sin("))
        return "sin";
    if (lower.includes("cos("))
        return "cos";
    if (lower.includes("tan("))
        return "tan";
    if (/\bsolutions?\b|\broots?\b/i.test(s))
        return "solutions";
    if (lower.includes("marginal density"))
        return "marginal_density";
    if (lower.includes("conditional density"))
        return "conditional_density";
    if (lower.includes("cov(") || lower.includes("covariance"))
        return "covariance";
    if (lower.includes("corr(") || lower.includes("correlation"))
        return "correlation";
    return "general";
}
function normalizeObjectToken(token) {
    return String(token || "")
        .toLowerCase()
        .replace(/\s+/g, "")
        .replace(/[{}]/g, "")
        .trim();
}
function extractScopeKey(segment) {
    const lower = String(segment || "").toLowerCase();
    if (/\b[a-z]\s*in\s*\[/.test(lower))
        return "domain_restricted";
    if (lower.includes("[0,2") && (lower.includes("pi") || lower.includes("π")))
        return "domain_restricted";
    return "default";
}
function extractIntentKey(segment) {
    const s = String(segment || "").toLowerCase();
    if (s.includes("and simplify"))
        return "with_simplify";
    if (s.includes("interpret"))
        return "with_interpretation";
    if (s.includes("by integrating over its support"))
        return "by_integrating_support";
    if (s.includes(" and "))
        return "compound";
    return "plain";
}
function normalizeSegmentForDedupe(segment) {
    return String(segment || "")
        .toLowerCase()
        .replace(/\s+/g, " ")
        .replace(/[^\w\s()[\]{}<>=|_/\\.^+-]/g, "")
        .trim();
}
// ============================================================================
// VALIDATION HELPER
// ============================================================================
/**
 * Check if input should be blocked due to multiple questions
 * Returns true if we should show the split UI
 */
function shouldShowSplitUI(text) {
    const result = detectMultiQuestion(text);
    // Only block on medium or high confidence
    return result.isMultiple && result.confidence !== 'low';
}
