export const INPUT_ERROR_INAPPROPRIATE = "Inappropriate language detected. Please rephrase.";
export const INPUT_ERROR_BLOCKED = "Input blocked. Please enter a valid math question.";
export const INPUT_ERROR_NOT_MATH = "Input must be a math question.";
export const INPUT_ERROR_EMPTY = "Please enter a math question.";
export const INPUT_ERROR_TOO_SHORT = "Please enter at least 3 characters.";
export const MIN_INPUT_LENGTH = 3;

const BAD_WORDS = [
    "fuck",
    "fucking",
    "shit",
    "shitty",
    "bitch",
    "asshole",
    "bastard",
    "dick",
    "cock",
    "pussy",
    "cunt",
    "nigger",
    "faggot",
    "slut",
    "whore",
    "motherfucker",
    "sex",
    "sexual",
    "porn",
    "porno",
    "pornography",
    "rape",
    "rapist",
    "cum",
    "ejaculate",
    "orgasm",
    "blowjob",
    "handjob",
    "anal",
    "penis",
    "vagina",
    "boobs",
    "tits",
    "nude",
    "nudes",
    "naked",
];

const FORBIDDEN_PATTERNS: RegExp[] = [
    /<script/i,
    /<\/\w/i,
    /\bimport\s+\w+/i,
    /\bfrom\s+[\w\.]+\s+import\b/i,
    /require\(/i,
    /eval\(/i,
    /exec\(/i,
    /subprocess/i,
    /system\(/i,
    /\bcat\s/i,
    /\bls\s/i,
    /\bdir\s/i,
    /\bchmod\s/i,
    /\bchown\s/i,
    /curl\s/i,
    /wget\s/i,
    /powershell/i,
    /cmd\.exe/i,
    /rm\s/i,
    /del\s/i,
    /drop\s+table/i,
    /insert\s+into/i,
    /update\s+\w+/i,
    /delete\s+from/i,
    /\bselect\s+.*\bfrom\b/i,
    /union\s+select/i,
    /https?:\/\//i,
    /\$\{/i,
    /\{\{/i,
];

export const isMathLikeInput = (value: string): boolean => {
    const normalized = value.trim().toLowerCase();
    if (!normalized) return false;

    if (/\d/.test(normalized)) return true;
    if (/[=<>+\-*/^]/.test(normalized)) return true;
    if (/\\(frac|sqrt|int|sum|lim|log|sin|cos|tan|theta|pi|alpha|beta|gamma|cdot|times)/i.test(normalized)) return true;
    if (/\b(solve|simplify|factor|expand|evaluate|derivative|integral|integrate|limit|graph|plot|domain|range|root|roots|intercept|slope|equation|function|probability|matrix|vector|geometry|algebra|calculus)\b/i.test(normalized)) return true;

    return false;
};

export const validateMathQuery = (value: unknown): string | null => {
    const normalized = String(value ?? "").trim().toLowerCase();
    if (!normalized) return INPUT_ERROR_EMPTY;
    if (normalized.length < MIN_INPUT_LENGTH) return INPUT_ERROR_TOO_SHORT;

    if (BAD_WORDS.some((word) => new RegExp(`\\b${word}\\b`, "i").test(normalized))) {
        return INPUT_ERROR_INAPPROPRIATE;
    }

    if (FORBIDDEN_PATTERNS.some((pattern) => pattern.test(normalized))) {
        return INPUT_ERROR_BLOCKED;
    }

    if (!isMathLikeInput(normalized)) {
        return INPUT_ERROR_NOT_MATH;
    }

    return null;
};

export const isInputTooShort = (value: string): boolean => {
    return String(value ?? "").trim().length < MIN_INPUT_LENGTH;
};

export const isBlockingInputError = (error?: string | null): boolean => {
    return error === INPUT_ERROR_INAPPROPRIATE || error === INPUT_ERROR_BLOCKED;
};
