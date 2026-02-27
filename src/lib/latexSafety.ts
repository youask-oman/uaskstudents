export function assertLatexSafe(latex: string, context = "latex"): string {
  const value = String(latex || "");
  if (!value.includes("\t")) return value;
  const preview = value.slice(0, 240).replace(/\n/g, "\\n");
  const message =
    'LaTeX contains a TAB character. This usually means "\\text" was decoded as "\\t". ' +
    "Stop double JSON parsing / ensure backslashes are escaped.";
  // Keep an explicit console log for diagnosis in all environments.
  // Throwing makes the source of corruption visible during rendering.
  console.error("[latex-safety]", { context, preview, message });
  throw new Error(message);
}

