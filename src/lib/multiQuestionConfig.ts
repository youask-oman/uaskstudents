/**
 * Multi-question detection configuration shared across detector and estimators.
 */

/** Minimum question marks to trigger multi-question signal */
export const MIN_QUESTION_MARKS_FOR_WARNING = 2;

/** Thresholds for detecting math-heavy content */
export const MATH_HEAVY_THRESHOLDS = {
    latexCommands: 2,
    operators: 5,
    digits: 10,
    parentheses: 6,
    equationLines: 2,
};

/** Regex patterns for list-style multi-question inputs */
export const LIST_MARKER_PATTERNS: RegExp[] = [
    /^\s*Q\d{1,3}[.:)\s-]*/gim,          // Q1, Q2, ...
    /^\s*\d{1,3}[.)]\s+/gm,              // 1) / 1. / 12)
    /^\s*\([a-z]\)\s+/gim,               // (a), (b)
    /^\s*[a-z]\)\s+/gim,                 // a), b)
    /^\s*(step|part)\s+(\d+|[a-z]+|\([ivx]+\))[:.)\s-]+/gim, // Step 1 / Part (i)
];

/** Connector words that weakly suggest multiple tasks */
export const CONNECTOR_PATTERN = /\b(also|then|next)\b/gi;

/** Backward-compatible aggregate patterns */
export const MULTI_QUESTION_PATTERNS: RegExp[] = [
    ...LIST_MARKER_PATTERNS,
    /\balso\s+(?:find|solve|calculate|compute|simplify|evaluate|show|prove)/gi,
    /\bthen\s+(?:find|solve|calculate|compute|simplify|evaluate|show|prove)/gi,
    /\bnext\s+(?:find|solve|calculate|compute|simplify|evaluate|show|prove)/gi,
];
