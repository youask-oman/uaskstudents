import base64
import io
import importlib.util
import logging
from pathlib import Path

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.bg_routers import local_router
from app.database import get_session
from app.services.math.error_localizer import FindErrorResult, LineCheckResult
from app.services.solve.canonicalization_service import canonicalization_service
from app.services.solve.solution_doc import apply_algebra_autocorrect, parse_solution_doc


def _load_safe_parser_class():
    module_path = Path(__file__).resolve().parents[1] / "app" / "services" / "visualization" / "safe_parser.py"
    spec = importlib.util.spec_from_file_location("runtime_audit_safe_parser", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SafeExpressionParser


def _set_audit_env(monkeypatch):
    monkeypatch.setenv("RUNTIME_AUDIT_LOGGING", "true")


def _get_audit_messages(caplog):
    return [r.getMessage() for r in caplog.records if "[RUNTIME_AUDIT]" in r.getMessage()]


def _make_png_b64(width: int = 80, height: int = 80) -> str:
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_canonicalization_runtime_proof(monkeypatch, caplog):
    _set_audit_env(monkeypatch)
    caplog.set_level(logging.DEBUG)

    c1, _ = canonicalization_service.normalize_math_object("sqrt(x+5) = x - 1", "solve_equation")
    c2a, _ = canonicalization_service.normalize_math_object("x^2 - 4", "solve_equation")
    c2b, _ = canonicalization_service.normalize_math_object("(x-2)(x+2)", "solve_equation")
    c3, _ = canonicalization_service.normalize_math_object("sin(x)^2 + cos(x)^2", "solve_equation")

    assert c1
    assert c2a == c2b
    assert c3 in {"false", "False"} or "Integer(1)" in c3

    msgs = _get_audit_messages(caplog)
    assert any("sympy_canonicalization" in msg for msg in msgs)


def test_solution_doc_verification_runtime_proof(monkeypatch, caplog):
    _set_audit_env(monkeypatch)
    caplog.set_level(logging.DEBUG)

    raw = r"""
## Step 1: Square both sides
x = x^2 - 4x + 4
## Step 2: Solve
x in {2, 4}
# Final Answer
Text: x in {2, 4}
LaTeX: x \in \{2,4\}
"""
    doc = parse_solution_doc(raw, problem_text="sqrt(x) = x - 2")
    corrected = apply_algebra_autocorrect(doc)
    final_text = (corrected.get("final_answer") or {}).get("text", "")
    constraints = corrected.get("domain_constraints") or []

    assert "4" in final_text
    assert any("x - 2" in item or "x" in item for item in constraints)

    raw2 = """
# Final Answer
    Text: x in {0, 2}
"""
    doc2 = parse_solution_doc(raw2, problem_text="(x+1)/(x-2)=3")
    corrected2 = apply_algebra_autocorrect(doc2)
    final_text2 = (corrected2.get("final_answer") or {}).get("text", "")
    constraints2 = corrected2.get("domain_constraints") or []
    assert final_text2
    assert ("7/2" in final_text2) or ("3.5" in final_text2)
    assert any("\\ne 0" in item or "x - 2" in item for item in constraints2)

    raw3 = "# Final Answer\nText: x in {-1, 1}\n"
    doc3 = parse_solution_doc(raw3, problem_text="log(x) = 0")
    corrected3 = apply_algebra_autocorrect(doc3)
    final_text3 = (corrected3.get("final_answer") or {}).get("text", "")
    constraints3 = corrected3.get("domain_constraints") or []
    assert "1" in final_text3
    assert any("> 0" in item for item in constraints3)

    msgs = _get_audit_messages(caplog)
    assert any("sympy_solution_doc_parse" in msg for msg in msgs)
    assert any("sympy_solution_doc_autocorrect" in msg for msg in msgs)
    assert any("sympy_solution_doc_verify_candidate" in msg for msg in msgs)


def test_safe_parser_sympy_numpy_runtime_proof(monkeypatch, caplog):
    _set_audit_env(monkeypatch)
    caplog.set_level(logging.DEBUG)
    SafeExpressionParser = _load_safe_parser_class()
    parser = SafeExpressionParser()
    x_values = np.linspace(-5, 5, 32)

    expr, err = parser.parse_expression("sin(x)/x")
    assert err is None and expr is not None
    y, eval_err = parser.evaluate_for_plotting("x**2 + 3*x - 1", x_values)
    assert eval_err is None and y is not None and y.shape[0] == 32

    bad_expr, bad_err = parser.parse_expression('__import__("os").system("echo hacked")')
    assert bad_expr is None and bad_err
    bad_expr2, bad_err2 = parser.parse_expression("lambda x: x")
    assert bad_expr2 is None and bad_err2

    msgs = _get_audit_messages(caplog)
    assert any("sympy_safe_parser_parse" in msg for msg in msgs)
    assert any("sympy_numpy_safe_parser_eval" in msg for msg in msgs)


def test_find_error_local_endpoint_runtime_proof(monkeypatch, session, caplog):
    _set_audit_env(monkeypatch)
    monkeypatch.setenv("FEATURE_LOCAL_FIND_ERROR", "true")
    caplog.set_level(logging.DEBUG)

    monkeypatch.setattr(local_router, "ocr_region_with_pix2text", lambda _: ("raw", "2(x+1)=2x+1", 0.95))

    app = FastAPI()
    app.include_router(local_router.router, prefix="/api/v1")
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)

    payload = {
        "image_data": _make_png_b64(),
        "selection_bbox": {"x": 0.1, "y": 0.1, "w": 0.8, "h": 0.8},
        "max_lines": 6,
    }
    res = client.post("/api/v1/find_error_local", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["analysis"]["first_wrong_line_index"] in (0, 1)

    msgs = _get_audit_messages(caplog)
    assert any("sympy_error_localizer_entry" in msg for msg in msgs)


def test_step_generator_low_confidence_path(monkeypatch, session):
    monkeypatch.setenv("FEATURE_LOCAL_FIND_ERROR", "true")
    called = {"step_generator": False}

    monkeypatch.setattr(local_router, "ocr_region_with_pix2text", lambda _: ("raw", "2x+1=7", 0.9))

    def _fake_find(*_args, **_kwargs):
        return FindErrorResult(
            first_wrong_line_index=None,
            what_is_wrong="No definite error found in the selected region.",
            minimal_fix="Try again",
            confidence=0.2,
            detected_format="equation",
            per_line=[LineCheckResult(ok=None, confidence=0.2, reason="low", minimal_fix="retry", debug={})],
        )

    def _fake_steps(_text):
        called["step_generator"] = True
        return ["forced low confidence steps"]

    monkeypatch.setattr(local_router, "find_first_error_from_ocr", _fake_find)
    monkeypatch.setattr(local_router, "generate_local_steps", _fake_steps)

    app = FastAPI()
    app.include_router(local_router.router, prefix="/api/v1")
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)

    payload = {
        "image_data": _make_png_b64(),
        "selection_bbox": {"x": 0.1, "y": 0.1, "w": 0.8, "h": 0.8},
        "max_lines": 6,
    }
    res = client.post("/api/v1/find_error_local", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert called["step_generator"] is True
    assert body["local_steps"] == ["forced low confidence steps"]
