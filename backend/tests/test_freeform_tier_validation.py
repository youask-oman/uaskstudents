from app.services.solve.freeform_solver import _coerce_research_plotly_block, validate_freeform_output


def _build_steps(count: int) -> str:
    return "\n".join(
        [f"Step {idx}: title: Action {idx} - Apply a valid algebraic/calculus operation." for idx in range(1, count + 1)]
    )


def test_validate_free_tier_accepts_6_to_10_steps_with_light_verification() -> None:
    output = (
        f"{_build_steps(6)}\n\n"
        "Verification:\n"
        "(1) Substitute the solution back into the original expression.\n"
        "(2) Confirm the transformed equation stays equivalent.\n\n"
        "Final Answer: x = 2\n"
        "LaTeX: x=2\n"
    )
    result = validate_freeform_output(output, tier="FREE", requested_mode="minimal")
    assert result["is_valid"] is True
    assert result["policy_tier"] == "FREE"


def test_validate_free_tier_rejects_plotly_block() -> None:
    output = (
        f"{_build_steps(6)}\n\n"
        "Verification:\n"
        "(1) Substitute into the equation.\n\n"
        "```json\n{\"data\":[],\"layout\":{}}\n```\n\n"
        "Final Answer: x = 2\n"
    )
    result = validate_freeform_output(output, tier="FREE", requested_mode="minimal")
    assert result["is_valid"] is False
    assert "no_plotly_json_block" in result["failed_checks"]


def test_validate_research_tier_requires_domain_verification_and_plotly() -> None:
    output = (
        "Domain constraints:\n"
        "- x is any real number for this polynomial/exponential integrand.\n\n"
        f"{_build_steps(12)}\n\n"
        "Verification:\n"
        "(1) Domain check: all terms are defined for real x.\n"
        "(2) Differentiate the antiderivative to recover the integrand.\n"
        "(3) Check edge-case behavior at x=0 and x=1.\n\n"
        "```json\n{\"data\":[{\"type\":\"scatter\",\"x\":[-1,0,1],\"y\":[0,1,2]}],\"layout\":{\"title\":\"Integrand\"}}\n```\n\n"
        "Final Answer: e^x(x^2-2x+2)+C\n"
        "LaTeX: e^x(x^2-2x+2)+C\n"
    )
    result = validate_freeform_output(output, tier="RESEARCH", requested_mode="minimal")
    assert result["is_valid"] is True
    assert result["policy_tier"] == "RESEARCH"


def test_validate_research_tier_flags_missing_plotly() -> None:
    output = (
        "Domain constraints:\n"
        "- x is any real number.\n\n"
        f"{_build_steps(12)}\n\n"
        "Verification:\n"
        "(1) Domain check.\n"
        "(2) Substitute/differentiate.\n"
        "(3) Edge-case check.\n\n"
        "Final Answer: e^x(x^2-2x+2)+C\n"
    )
    result = validate_freeform_output(output, tier="RESEARCH", requested_mode="minimal")
    assert result["is_valid"] is False
    assert "has_plotly_json_block" in result["failed_checks"]


def test_coerce_research_plotly_wraps_unfenced_plotly_json() -> None:
    raw = (
        "Step 1: title: Setup - Prepare expression.\n"
        "[ Plotly JSON ]\n"
        "{\"data\":[{\"type\":\"scatter\",\"x\":[0,1],\"y\":[1,2]}],\"layout\":{\"title\":\"Plot\"}}\n"
    )
    coerced = _coerce_research_plotly_block(raw, "RESEARCH")
    assert "```json" in coerced


def test_coerce_research_plotly_adds_fallback_when_missing() -> None:
    raw = "Step 1: title: Setup - Begin derivation.\nFinal Answer: x=1"
    coerced = _coerce_research_plotly_block(raw, "RESEARCH")
    assert "```json" in coerced
    assert '"data"' in coerced


def test_validate_research_tier_counts_markdown_step_and_verification_labels() -> None:
    output = (
        "Domain constraints:\n"
        "- x != 2\n\n"
        "**Step 1: title: Start - Rewrite equation.**\n"
        "**Step 2: title: Isolate - Move terms.**\n"
        "**Step 3: title: Simplify - Combine terms.**\n"
        "**Step 4: title: Transform - Normalize form.**\n"
        "**Step 5: title: Continue - Apply algebra.**\n"
        "**Step 6: title: Continue - Apply algebra.**\n"
        "**Step 7: title: Continue - Apply algebra.**\n"
        "**Step 8: title: Continue - Apply algebra.**\n"
        "**Step 9: title: Continue - Apply algebra.**\n"
        "**Step 10: title: Continue - Apply algebra.**\n"
        "**Step 11: title: Continue - Apply algebra.**\n"
        "**Step 12: title: Finish - Present result.**\n\n"
        "Verification:\n"
        "**Verification check 1: Domain check**\n"
        "**Verification check 2: Substitution check**\n"
        "**Verification check 3: Edge-case check**\n\n"
        "```json\n{\"data\":[{\"type\":\"scatter\",\"x\":[0,1],\"y\":[0,1]}],\"layout\":{\"title\":\"Plot\"}}\n```\n\n"
        "Final Answer: x=7/2\n"
    )
    result = validate_freeform_output(output, tier="RESEARCH", requested_mode="minimal")
    assert result["explicit_step_count"] == 12
    assert result["checks"]["verification_checks_min_3"] is True
    assert result["is_valid"] is True
