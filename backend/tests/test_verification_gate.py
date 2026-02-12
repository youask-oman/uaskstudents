from app.services.solve.verification_gate import verify_solve_result


def test_verification_gate_drops_extraneous_for_sqrt():
    result = {
        "final_answer": {"answer_text": "x in {2, 4}"},
    }
    meta = verify_solve_result("sqrt(x)=x-2", result, request_id="t1")
    assert meta["verified"] is True
    assert meta["verification_method"] == "symbolic"
    assert "4" in meta["final_solutions"]
    assert "2" not in meta["final_solutions"]
    assert any(item["candidate"] == "2" for item in meta["dropped_candidates"])


def test_verification_gate_enforces_rational_domain_restriction():
    result = {
        "final_answer": {"answer_text": "x in {0, 2, 7/2}"},
    }
    meta = verify_solve_result("(x+1)/(x-2)=3", result, request_id="t2")
    assert meta["verified"] is True
    assert "7/2" in meta["final_solutions"] or "3.5" in meta["final_solutions"]
    assert "2" not in meta["final_solutions"]
    assert any("x - 2 != 0" in item or "x-2 != 0" in item for item in meta["assumptions"])


def test_verification_gate_enforces_log_domain():
    result = {
        "final_answer": {"answer_text": "x in {-1, 1}"},
    }
    meta = verify_solve_result("log(x)=0", result, request_id="t3")
    assert meta["verified"] is True
    assert "1" in meta["final_solutions"]
    assert "-1" not in meta["final_solutions"]
    assert any("x > 0" in item for item in meta["assumptions"])


def test_verification_gate_symbolic_parse_failure_returns_none_method():
    meta = verify_solve_result("explain pythagorean theorem", {"final_answer": {"answer_text": "a^2+b^2=c^2"}})
    assert meta["verified"] is False
    assert meta["verification_method"] == "none"
