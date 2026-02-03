const SAFE_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);

const HAS_SCHEME_RE = /^[a-zA-Z][a-zA-Z\d+.-]*:/;

export interface LinkParseResult {
  ok: boolean;
  normalized?: string;
  error?: string;
}

const hasUnsafeProtocol = (value: string): boolean => /^javascript:/i.test(value) || /^data:/i.test(value);

export const normalizeLinkInput = (raw: string): string => {
  const trimmed = raw.trim();
  if (!trimmed) return "";
  if (HAS_SCHEME_RE.test(trimmed)) return trimmed;
  if (trimmed.includes("@") && !trimmed.includes(" ")) {
    return `mailto:${trimmed}`;
  }
  return `https://${trimmed}`;
};

export const validateAndNormalizeLink = (raw: string): LinkParseResult => {
  const normalized = normalizeLinkInput(raw);
  if (!normalized) return { ok: false, error: "Link is required." };
  if (hasUnsafeProtocol(normalized)) {
    return { ok: false, error: "Unsupported link protocol." };
  }
  try {
    const parsed = new URL(normalized);
    if (!SAFE_PROTOCOLS.has(parsed.protocol)) {
      return { ok: false, error: "Only http, https, and mailto links are allowed." };
    }
    if ((parsed.protocol === "http:" || parsed.protocol === "https:") && !parsed.hostname) {
      return { ok: false, error: "URL host is missing." };
    }
    return { ok: true, normalized: parsed.toString() };
  } catch {
    return { ok: false, error: "Invalid URL." };
  }
};

