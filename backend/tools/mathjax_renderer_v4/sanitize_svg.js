import sanitizeHtml from "sanitize-html";

const ALLOWED_TAGS = [
  "svg",
  "g",
  "path",
  "line",
  "rect",
  "circle",
  "ellipse",
  "polygon",
  "polyline",
  "text",
  "tspan",
  "defs",
  "clipPath",
  "title",
  "desc",
];

const ALLOWED_ATTRIBUTES = {
  "*": [
    "id",
    "class",
    "style",
    "transform",
    "fill",
    "fill-rule",
    "fill-opacity",
    "stroke",
    "stroke-width",
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-miterlimit",
    "stroke-dasharray",
    "stroke-dashoffset",
    "stroke-opacity",
    "opacity",
    "x",
    "y",
    "dx",
    "dy",
    "x1",
    "y1",
    "x2",
    "y2",
    "cx",
    "cy",
    "r",
    "rx",
    "ry",
    "d",
    "points",
    "width",
    "height",
    "viewBox",
    "preserveAspectRatio",
    "xmlns",
    "xmlns:xlink",
    "xml:space",
    "role",
    "aria-hidden",
    "focusable",
  ],
  use: ["href", "xlink:href"],
};

function stripDangerousAttributes(svg) {
  let out = String(svg || "");
  out = out.replace(/\son[a-zA-Z]+\s*=\s*(['"]).*?\1/gs, "");
  out = out.replace(/\s(?:href|xlink:href)\s*=\s*(['"])\s*javascript:.*?\1/gis, "");
  return out;
}

export function sanitizeSvg(svg) {
  const stripped = stripDangerousAttributes(svg);
  const sanitized = sanitizeHtml(stripped, {
    allowedTags: ALLOWED_TAGS,
    allowedAttributes: ALLOWED_ATTRIBUTES,
    allowedSchemes: [],
    allowProtocolRelative: false,
    parser: { lowerCaseTags: false },
    exclusiveFilter(frame) {
      const tag = (frame.tag || "").toLowerCase();
      return tag === "script" || tag === "foreignobject";
    },
  });
  return sanitized;
}

