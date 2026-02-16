/**
 * Multi-Question Detector
 * 
 * Detects when user input contains multiple questions and provides
 * auto-split functionality to separate them.
 */

import { MULTI_QUESTION_PATTERNS, MIN_QUESTION_MARKS_FOR_WARNING } from './tokenBudget';

// ============================================================================
// TYPES
// ============================================================================

export interface MultiQuestionResult {
    /** Whether multiple questions were detected */
    isMultiple: boolean;
    /** Confidence level: 'high' if multiple strong signals, 'medium' for weaker signals */
    confidence: 'high' | 'medium' | 'low';
    /** Number of question marks found */
    questionMarks: number;
    /** Patterns that matched */
    matchedPatterns: string[];
    /** Suggested split points (if applicable) */
    suggestedSplits: string[];
}

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
export function detectMultiQuestion(text: string): MultiQuestionResult {
    const matchedPatterns: string[] = [];

    // Count question marks
    const questionMarks = (text.match(/\?/g) || []).length;
    if (questionMarks >= MIN_QUESTION_MARKS_FOR_WARNING) {
        matchedPatterns.push(`${questionMarks} question marks`);
    }

    // Check each pattern
    // Check each pattern
    for (const pattern of MULTI_QUESTION_PATTERNS) {
        // Reset lastIndex for global patterns
        pattern.lastIndex = 0;
        const matches = text.match(pattern);

        if (!matches || matches.length === 0) continue;

        // Distinguish between connectors (also/then/next) and list markers (1), Q1, etc.)
        // Connectors imply multiplicity even if appearing once.
        // List markers must appear at least twice to imply a list.
        const firstMatch = matches[0].trim().toLowerCase();
        const isConnector = firstMatch.startsWith('also') ||
            firstMatch.startsWith('then') ||
            firstMatch.startsWith('next');

        if (isConnector) {
            matchedPatterns.push(`Pattern: ${matches[0]}`);
        } else if (matches.length >= 2) {
            matchedPatterns.push(`${matches.length}x pattern '${matches[0]}'`);
        }
    }

    // Check for multiple equation blocks separated by blank lines
    const blocks = text.split(/\n\s*\n/).filter(b => b.trim().length > 0);
    const equationBlocks = blocks.filter(block => /[=]/.test(block));
    if (equationBlocks.length >= 2) {
        matchedPatterns.push(`${equationBlocks.length} equation blocks`);
    }

    // Determine confidence
    let confidence: 'high' | 'medium' | 'low' = 'low';
    if (matchedPatterns.length >= 3) {
        confidence = 'high';
    } else if (matchedPatterns.length >= 1) {
        confidence = 'medium';
    }

    // Generate suggested splits
    const suggestedSplits = confidence !== 'low' ? autoSplitQuestions(text) : [];

    return {
        isMultiple: matchedPatterns.length >= 1,
        confidence,
        questionMarks,
        matchedPatterns,
        suggestedSplits,
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
export function autoSplitQuestions(text: string): string[] {
    // Try numbered patterns first
    const numberedSplit = splitByNumberedPatterns(text);
    if (numberedSplit.length >= 2) {
        return numberedSplit;
    }

    // Try question mark boundaries
    const questionSplit = splitByQuestionMarks(text);
    if (questionSplit.length >= 2) {
        return questionSplit;
    }

    // Try blank-line blocks
    const blockSplit = splitByBlankLines(text);
    if (blockSplit.length >= 2) {
        return blockSplit;
    }

    // No good split found
    return [text];
}

/**
 * Split by numbered patterns (Q1, 1), (a), etc.)
 */
function splitByNumberedPatterns(text: string): string[] {
    const normalized = text.replace(/\r\n/g, "\n");

    const splitByLineMarkers = (source: string, marker: RegExp): string[] => {
        const matches = [...source.matchAll(marker)];
        if (matches.length < 2) return [];
        const parts: string[] = [];
        for (let i = 0; i < matches.length; i += 1) {
            const start = matches[i].index ?? 0;
            const end = i + 1 < matches.length ? (matches[i + 1].index ?? source.length) : source.length;
            const raw = source.slice(start, end).trim();
            const cleaned = raw
                .replace(/^\s*Q\d{1,3}[.:)\s-]*/i, "")
                .replace(/^\s*\d{1,3}[.)]\s*/, "")
                .trim();
            if (cleaned.length > 0) parts.push(cleaned);
        }
        return cleanSplits(parts);
    };

    // Try Q1/Q2... at start of lines.
    const qLineSplit = splitByLineMarkers(normalized, /^\s*Q\d{1,3}[.:)\s-]*/gim);
    if (qLineSplit.length >= 2) return qLineSplit;

    // Try numeric 1), 2), ... 10), 11), ...
    const numericLineSplit = splitByLineMarkers(normalized, /^\s*\d{1,3}[.)]\s+/gm);
    if (numericLineSplit.length >= 2) return numericLineSplit;

    // Handle inline numbering in the same physical line: "... 10) ... 11) ..."
    const withInlineBreaks = normalized.replace(/([.?!:;])\s+(\d{1,3}[.)]\s+)/g, "$1\n$2");
    const numericInlineSplit = splitByLineMarkers(withInlineBreaks, /^\s*\d{1,3}[.)]\s+/gm);
    if (numericInlineSplit.length >= 2) return numericInlineSplit;

    // Try (a), (b), ...
    const letterPattern = /^\s*\([a-e]\)\s*/gm;
    const letterParts = withInlineBreaks.split(letterPattern).filter(p => p.trim().length > 1);
    if (letterParts.length >= 2) return cleanSplits(letterParts);

    return [];
}

/**
 * Split by question marks
 */
function splitByQuestionMarks(text: string): string[] {
    // Split on ? but keep context
    const parts = text.split(/\?\s*/).filter(p => p.trim().length > 5);
    return parts.map(p => p.trim() + (p.endsWith('?') ? '' : '?'));
}

/**
 * Split by blank lines
 */
function splitByBlankLines(text: string): string[] {
    return text.split(/\n\s*\n/).filter(p => p.trim().length > 5).map(p => p.trim());
}

/**
 * Clean up splits: remove empty, trim, filter too-short
 */
function cleanSplits(parts: string[]): string[] {
    return parts
        .map(p => p.trim())
        .filter(p => p.length > 5)  // Minimum meaningful length
        .filter(p => !/^[1-9a-e]$/i.test(p)); // Filter out lone numbers/letters
}

// ============================================================================
// VALIDATION HELPER
// ============================================================================

/**
 * Check if input should be blocked due to multiple questions
 * Returns true if we should show the split UI
 */
export function shouldShowSplitUI(text: string): boolean {
    const result = detectMultiQuestion(text);
    // Only block on medium or high confidence
    return result.isMultiple && result.confidence !== 'low';
}
