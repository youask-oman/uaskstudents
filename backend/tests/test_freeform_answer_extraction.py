from app.services.solve.freeform_solver import extract_answer_from_freeform


def test_extract_answer_prefers_boxed_value() -> None:
    text = (
        "Step 1: simplify.\n"
        "Final Answer:\n"
        "\\[\n"
        "\\boxed{x = 11}\n"
        "\\]\n"
    )
    assert extract_answer_from_freeform(text) == "x = 11"


def test_extract_answer_uses_last_equation_when_final_section_missing() -> None:
    text = (
        "Step 1: State identity.\n"
        "\\[\n"
        "\\sin^2(x) + \\cos^2(x) = 1\n"
        "\\]\n"
        "Verification:\n"
        "(1) Domain check\n"
        "(2) Sub\n"
    )
    assert extract_answer_from_freeform(text) == "\\sin^2(x) + \\cos^2(x) = 1"


def test_extract_answer_avoids_numbered_noise_lines() -> None:
    text = "Verification:\n(1) Domain check\n(2) Sub\n"
    assert extract_answer_from_freeform(text) is None
