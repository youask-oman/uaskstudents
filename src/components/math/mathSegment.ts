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
        const next = pickNext(nextInline, nextBlock);

        if (next.index === -1) {
            segments.push({ type: "text", value: content.slice(cursor) });
            break;
        }

        if (next.index > cursor) {
            segments.push({ type: "text", value: content.slice(cursor, next.index) });
        }

        const closeDelim = next.type === "block_math" ? "\\]" : "\\)";
        const closeIndex = findDelimiter(content, closeDelim, next.index + 2);
        if (closeIndex === -1) {
            segments.push({ type: "text", value: content.slice(next.index) });
            break;
        }

        const value = content.slice(next.index + 2, closeIndex);
        segments.push({ type: next.type, value });
        cursor = closeIndex + 2;
    }

    return segments;
};

const pickNext = (inlineIndex: number, blockIndex: number) => {
    if (inlineIndex === -1 && blockIndex === -1) {
        return { index: -1, type: "text" as const };
    }
    if (inlineIndex === -1) {
        return { index: blockIndex, type: "block_math" as const };
    }
    if (blockIndex === -1) {
        return { index: inlineIndex, type: "inline_math" as const };
    }
    if (blockIndex <= inlineIndex) {
        return { index: blockIndex, type: "block_math" as const };
    }
    return { index: inlineIndex, type: "inline_math" as const };
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
