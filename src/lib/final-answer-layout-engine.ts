/**
 * FinalAnswerLayoutEngine
 * 
 * Shared logic for parsing and normalizing LaTeX content for display.
 * Ensures deterministic line breaking and consistent rendering across
 * web preview and DOCX/PDF export.
 */

export type LayoutBlock =
    | { kind: "math"; latex: string; display: true }
    | { kind: "text"; text: string };

/**
 * Track brace depth to find top-level separators
 */
interface TokenizerState {
    depth: number;
    inTextCommand: boolean;
    textBraceDepth: number;
}

/**
 * Split LaTeX string at top-level separators while respecting brace nesting and \text{} blocks
 */
function tokenizeAtTopLevel(latex: string, separator: RegExp): string[] {
    const results: string[] = [];
    let current = "";
    let state: TokenizerState = { depth: 0, inTextCommand: false, textBraceDepth: 0 };
    let i = 0;

    while (i < latex.length) {
        const char = latex[i];
        const remaining = latex.slice(i);

        // Check for \text{...} or similar text commands
        const textMatch = remaining.match(/^\\(text|textrm|textbf|textit|mathrm|mbox)\{/);
        if (textMatch && state.depth === 0 && !state.inTextCommand) {
            current += textMatch[0];
            i += textMatch[0].length;
            state.inTextCommand = true;
            state.textBraceDepth = 1;
            continue;
        }

        // Track text command brace depth
        if (state.inTextCommand) {
            if (char === "{") {
                state.textBraceDepth++;
            } else if (char === "}") {
                state.textBraceDepth--;
                if (state.textBraceDepth === 0) {
                    state.inTextCommand = false;
                }
            }
            current += char;
            i++;
            continue;
        }

        // Check for escaped characters
        if (char === "\\") {
            // Check for \\ (line break) - this is a special separator
            if (latex[i + 1] === "\\") {
                if (separator.source === "\\\\\\\\") {
                    // We're splitting on \\
                    if (state.depth === 0) {
                        results.push(current.trim());
                        current = "";
                        i += 2;
                        continue;
                    }
                }
                current += "\\\\";
                i += 2;
                continue;
            }
            // Check for \; \, \: etc
            if (/^\\[;:,!]/.test(remaining)) {
                current += remaining.slice(0, 2);
                i += 2;
                continue;
            }
            // Other escaped commands
            current += char;
            i++;
            continue;
        }

        // Track brace depth
        if (char === "{" || char === "[" || char === "(") {
            state.depth++;
        } else if (char === "}" || char === "]" || char === ")") {
            state.depth = Math.max(0, state.depth - 1);
        }

        // Check for separator at top level
        if (state.depth === 0 && separator.source !== "\\\\\\\\") {
            const sepMatch = remaining.match(separator);
            if (sepMatch && sepMatch.index === 0) {
                results.push(current.trim());
                current = "";
                i += sepMatch[0].length;
                continue;
            }
        }

        current += char;
        i++;
    }

    if (current.trim()) {
        results.push(current.trim());
    }

    return results.filter(Boolean);
}

/**
 * Check if a clause contains a relation operator at the top level
 */
function findAlignmentPoint(clause: string): { before: string; operator: string; after: string } | null {
    const operators = ["=", "\\approx", "\\to", "\\Rightarrow", "\\rightarrow", "\\leq", "\\geq", "\\neq", "\\equiv", "\\sim", "\\simeq", "\\cong", "\\propto", "\\parallel", "\\perp"];

    let depth = 0;
    let inTextCommand = false;
    let textBraceDepth = 0;

    for (let i = 0; i < clause.length; i++) {
        const char = clause[i];
        const remaining = clause.slice(i);

        // Handle \text{...}
        const textMatch = remaining.match(/^\\(text|textrm|textbf|textit|mathrm|mbox)\{/);
        if (textMatch && depth === 0 && !inTextCommand) {
            i += textMatch[0].length - 1;
            inTextCommand = true;
            textBraceDepth = 1;
            continue;
        }

        if (inTextCommand) {
            if (char === "{") textBraceDepth++;
            else if (char === "}") {
                textBraceDepth--;
                if (textBraceDepth === 0) inTextCommand = false;
            }
            continue;
        }

        // Track depth
        if (char === "{" || char === "[" || char === "(") depth++;
        else if (char === "}" || char === "]" || char === ")") depth = Math.max(0, depth - 1);

        // Check for operators at top level
        if (depth === 0) {
            for (const op of operators) {
                if (remaining.startsWith(op)) {
                    return {
                        before: clause.slice(0, i).trim(),
                        operator: op,
                        after: clause.slice(i + op.length).trim(),
                    };
                }
            }
        }
    }

    return null;
}

/**
 * Check if a string looks like it's primarily text (not math)
 */
function isTextBlock(content: string): boolean {
    const trimmed = content.trim();

    // Check for "Expected classification:" or similar patterns
    if (/^\\text\{[^}]*:\s*\}/i.test(trimmed)) return true;
    if (/^(Expected|Note|Classification|Result|Answer):/i.test(trimmed)) return true;

    // If it starts with \text{...} and that's most of the content
    const textMatch = trimmed.match(/^\\text\{([^}]+)\}/);
    if (textMatch && textMatch[0].length > trimmed.length * 0.7) return true;

    return false;
}

/**
 * Extract text content from \text{...} blocks
 */
function extractTextContent(latex: string): string {
    return latex
        .replace(/\\text\{([^}]+)\}/g, "$1")
        .replace(/\\\\/g, " ")
        .replace(/\\[;:,!]/g, " ")
        .replace(/\s+/g, " ")
        .trim();
}

/**
 * Normalize clauses into an aligned LaTeX environment
 */
function buildAlignedEnvironment(clauses: string[]): string {
    if (clauses.length === 0) return "";
    if (clauses.length === 1) {
        return clauses[0];
    }

    const alignedLines: string[] = [];

    for (const clause of clauses) {
        const alignment = findAlignmentPoint(clause);
        if (alignment) {
            // Remove trailing comma if present
            let after = alignment.after.replace(/,\s*$/, "");
            alignedLines.push(`${alignment.before} &${alignment.operator} ${after}`);
        } else {
            // No alignment point, just add the line
            alignedLines.push(`&${clause}`);
        }
    }

    return `\\begin{aligned}\n${alignedLines.join(",\\\\\n")}\n\\end{aligned}`;
}

/**
 * Main function: Parse LaTeX and split into normalized blocks
 */
export function parseLatexToBlocks(rawLatex: string): LayoutBlock[] {
    if (!rawLatex || !rawLatex.trim()) {
        return [];
    }

    const blocks: LayoutBlock[] = [];
    let latex = rawLatex.trim();

    // Step 1: Split by explicit \\ line breaks first
    const lineBreakParts = tokenizeAtTopLevel(latex, /\\\\/);

    // Collect math clauses and text blocks separately
    const mathClauses: string[] = [];

    for (const part of lineBreakParts) {
        const trimmed = part.trim();
        if (!trimmed) continue;

        // Check if this is a text boundary
        if (isTextBlock(trimmed)) {
            // Flush any accumulated math clauses
            if (mathClauses.length > 0) {
                const alignedMath = buildAlignedEnvironment(mathClauses);
                blocks.push({ kind: "math", latex: alignedMath, display: true });
                mathClauses.length = 0;
            }
            // Add text block
            blocks.push({ kind: "text", text: extractTextContent(trimmed) });
            continue;
        }

        // Check for embedded text boundaries like "...\text{Expected:}..."
        const textBoundaryMatch = trimmed.match(/^(.*)\\text\{([^}]*:)\s*\}(.*)$/);
        if (textBoundaryMatch) {
            const [, beforeText, label, afterText] = textBoundaryMatch;

            if (beforeText.trim()) {
                // Split beforeText by semicolons for better alignment
                const semicolonParts = tokenizeAtTopLevel(beforeText, /;/);
                mathClauses.push(...semicolonParts);
            }

            // Flush math clauses
            if (mathClauses.length > 0) {
                const alignedMath = buildAlignedEnvironment(mathClauses);
                blocks.push({ kind: "math", latex: alignedMath, display: true });
                mathClauses.length = 0;
            }

            // Add the text label and remaining content
            if (afterText.trim()) {
                blocks.push({ kind: "text", text: `${label} ${extractTextContent(afterText)}` });
            } else {
                blocks.push({ kind: "text", text: label });
            }
            continue;
        }

        // Step 2: Split by semicolons at top level
        const semicolonParts = tokenizeAtTopLevel(trimmed, /;/);
        mathClauses.push(...semicolonParts);
    }

    // Flush remaining math clauses
    if (mathClauses.length > 0) {
        const alignedMath = buildAlignedEnvironment(mathClauses);
        blocks.push({ kind: "math", latex: alignedMath, display: true });
    }

    return blocks;
}

/**
 * Render blocks back to LaTeX for display
 * This creates properly wrapped math with line breaks
 */
export function blocksToDisplayLatex(blocks: LayoutBlock[]): string {
    const parts: string[] = [];

    for (const block of blocks) {
        if (block.kind === "math") {
            parts.push(block.latex);
        } else {
            parts.push(`\\text{${block.text}}`);
        }
    }

    return parts.join("\n\n");
}

/**
 * Convert raw latex to a normalized, well-aligned display format
 */
export function normalizeLatexForDisplay(rawLatex: string): string {
    const blocks = parseLatexToBlocks(rawLatex);

    if (blocks.length === 0) {
        return rawLatex;
    }

    // If we only have one math block and it's already compact, return as-is
    if (blocks.length === 1 && blocks[0].kind === "math") {
        return blocks[0].latex;
    }

    return blocksToDisplayLatex(blocks);
}

/**
 * Check if LaTeX content is likely to overflow and needs wrapping
 */
export function needsWrapping(latex: string, maxCharsPerLine: number = 80): boolean {
    // Simple heuristic: check if any "line" exceeds the threshold
    const lines = latex.split(/\\\\|\n/);
    return lines.some(line => line.length > maxCharsPerLine);
}

/**
 * Wrap long math expressions for better display
 */
export function wrapLongMath(latex: string, maxWidth: number = 60): string {
    // If it already has alignment, don't modify
    if (/\\begin\{(aligned|align|gather|split)\}/.test(latex)) {
        return latex;
    }

    // Parse and normalize
    return normalizeLatexForDisplay(latex);
}
