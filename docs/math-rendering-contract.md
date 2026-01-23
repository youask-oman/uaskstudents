# Math Rendering Contract

## Delimiter Rules

1) Prose with embedded math (chat messages, explanations)
   - Inline math: `\\( ... \\)`
   - Block math: `\\[ ... \\]`
   - Do not use `$...$` or `$$...$$` for new content.

2) Math-only fields stored in JSON (e.g., `step.math_latex`, `final_answer.answer_latex`, `verification.work_latex`)
   - Store raw LaTeX with no delimiters.
   - The renderer wraps raw LaTeX in `\\( ... \\)` or `\\[ ... \\]` based on mode.

3) Legacy normalization (prose only)
   - Convert fenced ```latex blocks to `\\[ ... \\]`.
   - Convert `$$...$$` to `\\[ ... \\]`.
   - Convert safe, unambiguous `$...$` to `\\( ... \\)`.
   - Escape ambiguous or currency `$` as `\\$`.

## Rendering Modes

- `mode="prose"`: mixed text + math, expects delimiters.
- `mode="inline"`: raw LaTeX rendered inline.
- `mode="block"`: raw LaTeX rendered as display math.

## Error Handling

- Malformed LaTeX must not crash the UI.
- Render raw LaTeX in a code-like fallback and log telemetry counters.

## Streaming Content

- Use `dynamic` to debounce updates and typeset only on chunk boundaries.
- Avoid re-typesetting entire pages on small updates.
