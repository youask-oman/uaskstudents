import uuid

from scripts.ci_proof_real_solve_billing import run_ci_proof


def test_ci_proof_real_solve_billing():
    run_id = str(uuid.uuid4())
    summary = run_ci_proof(run_id)

    # Basic sanity
    assert summary["run_id"] == run_id
    assert len(summary["solve_results"]) == 3

    # Credits must drop by expected amounts (flat tier pricing)
    before = summary["wallet_before"]
    after = summary["wallet_after"]

    assert round(before["student_a"] - after["student_a"], 6) == 5
    assert round(before["student_b"] - after["student_b"], 6) == 17

    # Ensure attempts exist for each solve
    for r in summary["solve_results"]:
        assert r["attempt_id"]
        assert r["request_id"]

    # Billing ledger entries for solves (BillingLedger preferred, UsageLedger fallback)
    ledger_rows = summary.get("solve_ledger_rows", []) or summary.get("solve_usage_rows", [])
    if summary.get("solve_ledger_rows"):
        ledger_map = {row.get("request_id"): row for row in ledger_rows}
        credit_field = "credits_charged"
    else:
        ledger_map = {row.get("reference_id"): row for row in ledger_rows}
        credit_field = "amount"
    expected = {r["request_id"]: r["expected_credits"] for r in summary["solve_results"]}
    for req_id, credits in expected.items():
        assert req_id in ledger_map
        assert round(abs(float(ledger_map[req_id].get(credit_field) or 0)), 6) == credits
