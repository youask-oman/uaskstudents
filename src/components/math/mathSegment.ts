export type MathSegment =
    | { type: "text"; value: string }
    | { type: "inline_math"; value: string }
    | { type: "block_math"; value: string };

export const segmentMath = (content: string): MathSegment[] => {
    if (!content) return [{ type: "text", value: "" }];

    const segments: MathSegment[] = [];
    let cursor = 0;

    while (cursor < content.length) {
        const nextInline = findDelimiter(content, "\\(", cursor);
        const nextBlock = findDelimiter(content, "\\[", cursor);

        // Also look for naked backslash commands (e.g. \sqrt)
        // We look for a backslash followed by a letter, not preceded by a delimiter trigger
        let nakedBackslash = -1;
        const bsRegex = /\\([a-zA-Z]+)/g;
        bsRegex.lastIndex = cursor;
        const match = bsRegex.exec(content);
        if (match && !isEscaped(content, match.index)) {
            // Ensure this backslash isn't the start of \( or \[ (already handled)
            if (content[match.index + 1] !== '(' && content[match.index + 1] !== '[') {
                nakedBackslash = match.index;
            }
        }

        const next = pickNext(nextInline, nextBlock, nakedBackslash);

        if (next.index === -1) {
            segments.push({ type: "text", value: content.slice(cursor) });
            break;
        }

        if (next.index > cursor) {
            segments.push({ type: "text", value: content.slice(cursor, next.index) });
        }

        if (next.type === "naked_command") {
            const rest = content.slice(next.index);
            // Match the command (\sqrt) plus optional trailing brackets: {}, [], ()
            const fullMatch = rest.match(/^\\([a-zA-Z]+)(?:\{[^{}]*\}|\[[^[\]]*\]|\([^()]*\))*/);
            const cmdLen = fullMatch ? fullMatch[0].length : 1;
            segments.push({ type: "inline_math", value: content.slice(next.index, next.index + cmdLen) });
            cursor = next.index + cmdLen;
            continue;
        }

        const closeDelim = next.type === "block_math" ? "\\]" : "\\)";
        const closeIndex = findDelimiter(content, closeDelim, next.index + 2);
        if (closeIndex === -1) {
            // Keep unmatched opening delimiters as plain text so we do not
            // render the rest of a streaming/truncated message as math.
            segments.push({ type: "text", value: content.slice(next.index, next.index + 2) });
            cursor = next.index + 2;
            continue;
        }

        const value = content.slice(next.index + 2, closeIndex);
        segments.push({ type: next.type === "block_math" ? "block_math" : "inline_math", value });
        cursor = closeIndex + 2;
    }

    return segments;
};

const pickNext = (inlineIndex: number, blockIndex: number, nakedIndex: number) => {
    let best = { index: -1, type: "text" as "text" | "inline_math" | "block_math" | "naked_command" };

    const update = (idx: number, type: "inline_math" | "block_math" | "naked_command") => {
        if (idx !== -1 && (best.index === -1 || idx < best.index)) {
            best = { index: idx, type };
        }
    };

    update(inlineIndex, "inline_math");
    update(blockIndex, "block_math");
    update(nakedIndex, "naked_command");

    return best;
};

const isEscaped = (text: string, index: number) => {
    let backslashes = 0;
    let cursor = index - 1;
    while (cursor >= 0 && text[cursor] === "\\") {
        backslashes += 1;
        cursor -= 1;
    }
    return backslashes % 2 === 1;
};

const findDelimiter = (text: string, delimiter: string, fromIndex: number) => {
    let location = text.indexOf(delimiter, fromIndex);
    while (location !== -1) {
        if (!isEscaped(text, location)) return location;
        location = text.indexOf(delimiter, location + 1);
    }
    return -1;
};
