## Math Rendering Guidance

- For the MathJax renderer, prefer explicit delimiters: use `\(...\)` for inline math and `\[...\]` for display math so the renderer can keep spaces intact.
- Avoid emitting `$...$` or `$$...$$` unless you are certain the delimiters are correctly paired; stray dollars are escaped and rendered as literal text to prevent mangling.
- When referencing the feature flag, set `NEXT_PUBLIC_MATH_RENDERER=mathjax` to opt into the MathJax renderer for step explanations (it defaults to `katex` for backwards compatibility).

