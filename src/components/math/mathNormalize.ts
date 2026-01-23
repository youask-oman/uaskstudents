export const normalizeProseMath = (content: string): string => {
    if (!content) return "";
    let text = content;

    text = convertLatexFences(text);
    text = convertDisplayMath(text);

    const lines = text.split("\n");
    const normalized = lines.map((line) => normalizeInlineDollars(line));
    return normalized.join("\n");
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

const convertLatexFences = (text: string) => {
    return text.replace(/```(?:latex|tex)\s*([\s\S]*?)```/g, (_match, inner) => {
        const trimmed = String(inner || "").trim();
        if (!trimmed) return "";
        return `\\[\n${trimmed}\n\\]`;
    });
};

const convertDisplayMath = (text: string) => {
    let cursor = 0;
    let output = "";

    while (cursor < text.length) {
        const start = findDelimiter(text, "$$", cursor);
        if (start === -1) {
            output += text.slice(cursor);
            break;
        }

        output += text.slice(cursor, start);
        const closing = findDelimiter(text, "$$", start + 2);
        if (closing === -1) {
            output += "\\$\\$";
            cursor = start + 2;
            continue;
        }

        const block = text.slice(start + 2, closing);
        output += `\\[\n${block}\n\\]`;
        cursor = closing + 2;
    }

    return output;
};

const normalizeInlineDollars = (line: string) => {
    const dollarIndexes: number[] = [];
    for (let i = 0; i < line.length; i += 1) {
        if (line[i] === "$" && !isEscaped(line, i)) {
            dollarIndexes.push(i);
        }
    }

    if (dollarIndexes.length === 0) return line;
    if (dollarIndexes.length % 2 === 1) {
        return escapeAllDollars(line);
    }

    let output = "";
    let cursor = 0;
    for (let i = 0; i < dollarIndexes.length; i += 2) {
        const start = dollarIndexes[i];
        const end = dollarIndexes[i + 1];
        output += line.slice(cursor, start);

        const inner = line.slice(start + 1, end);
        if (isSafeInlinePair(inner)) {
            output += `\\(${inner.trim()}\\)`;
        } else {
            output += `\\$${inner}\\$`;
        }
        cursor = end + 1;
    }

    output += line.slice(cursor);
    return output;
};

const escapeAllDollars = (text: string) => {
    let output = "";
    for (let i = 0; i < text.length; i += 1) {
        const ch = text[i];
        if (ch === "$" && !isEscaped(text, i)) {
            output += "\\$";
        } else {
            output += ch;
        }
    }
    return output;
};

const isSafeInlinePair = (inner: string) => {
    const trimmed = inner.trim();
    if (!trimmed) return false;
    if (/^[\d.,]+$/.test(trimmed)) return false;
    if (/\\[a-zA-Z]+/.test(trimmed)) return true;
    if (/[=+\-*/^_<>]/.test(trimmed)) return true;
    if (/\\begin\{/.test(trimmed)) return true;
    if (/^[a-zA-Z]$/.test(trimmed)) return true;
    return false;
};
