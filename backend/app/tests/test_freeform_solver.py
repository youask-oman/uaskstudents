from pathlib import Path

from app.services.solve.freeform_solver import (
    archive_freeform_output,
    build_freeform_prompt,
    load_default_freeform_prompt_template,
    should_use_freeform_output,
    validate_freeform_output,
)


def _good_freeform_text() -> str:
    lines = []
    for idx in range(1, 13):
        lines.append(f"Step {idx}: Explain operation {idx} in detail for the equation.")
        lines.append("title: precise algebra micro-step")
        lines.append("This sentence explains one small manipulation and why it is valid.")
    lines.append("Domain constraints:")
    lines.append("- Radicand must be non-negative.")
    lines.append("- Denominator must be non-zero.")
    lines.append("Verification:")
    lines.append("(1) Domain check: valid.")
    lines.append("(2) Substitution check: valid.")
    lines.append("(3) Extraneous check: valid.")
    lines.append("```json")
    lines.append('{"data":[{"type":"scatter","x":[0,1,2],"y":[0,1,4]}],"layout":{"title":"Plot"}}')
    lines.append("```")
    lines.append("Final answer: x = 2")
    filler = " Additional explanation for clarity and rigor." * 45
    return "\n".join(lines) + filler


def test_validate_freeform_output_accepts_contract_shape():
    text = _good_freeform_text()
    result = validate_freeform_output(text)
    assert result["is_valid"] is True
    assert result["checks"]["steps_min_12"] is True
    assert result["checks"]["char_count_min_1800"] is True


def test_build_freeform_prompt_injects_problem():
    template = "Solve this:\n{PROBLEM}\nReturn detailed steps."
    prompt = build_freeform_prompt("x^2 = 9", template)
    assert "{PROBLEM}" not in prompt
    assert "x^2 = 9" in prompt


def test_default_freeform_template_exists():
    template = load_default_freeform_prompt_template()
    assert "{PROBLEM}" in template


def test_archive_freeform_output_writes_utf8_file():
    path = archive_freeform_output(
        request_id="req-123",
        provider="ollama",
        model="mightykatun/qwen2.5-math:7b",
        attempt_number=1,
        output_text="Step 1: √x = 2",
    )
    output_path = Path(path)
    assert output_path.exists()
    assert output_path.suffix == ".md"
    assert "solver_outputs" in str(output_path)


def test_should_use_freeform_output_for_default_ollama_model(monkeypatch):
    monkeypatch.setenv("SOLVER_OUTPUT_MODE_DEFAULT", "FREEFORM")
    monkeypatch.setenv("OLLAMA_MODEL", "mightykatun/qwen2.5-math:7b")
    assert should_use_freeform_output("ollama", "mightykatun/qwen2.5-math:7b") is True
    assert should_use_freeform_output("openai", "gpt-5-mini") is False
