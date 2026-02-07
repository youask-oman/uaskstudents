# Backend Deep Dive: "Missing Specifics" Verification

## A) Current "Math Truth" Source

1.  **Do we execute ANY CAS for correctness?**
    *   **Answer:** **No, not for solving.** The LLM is the sole source of truth for the solution steps and final answer.
    *   **SymPy Usage:** We *do* use `sympy` in `backend/app/services/visualization/safe_parser.py`, but **strictly for visualization** (plotting graphs based on the LLM's output). It is **not** used to verify the LLM's algebraic steps.
2.  **Artifacts:**
    *   `SafeExpressionParser` (in `safe_parser.py`) parses expressions like `"y=x^2"` to generate point data for the frontend. These are ephemeral during the request and not stored as "truth".

## B) Persistence & Storage (The "Ledger")

3.  **Persistence Timing (Pre vs. Post):**
    *   **Answer:** **Post-Success Only.**
    *   **Code Path:** In `api.py:solve_problem`:
        1.  `await solver.solve(...)` (Lines 3981)
        2.  `session.add(new_chat)` (Lines 4030) - **Writes happen here.**
    *   **Implication:** If the solver crashes or times out *during* generation, **nothing is written** to `SolveSession` or `ChatMessage`. We have no DB record of failed attempts (only file-based logs).
4.  **Raw OpenAI Responses:**
    *   **Answer:** **Partially Stored.**
    *   **Location:** `ChatMessage` table.
    *   **Column:** `content` stores the **raw string** text (e.g., the JSON string before parsing). `structured_data` stores the **parsed JSON**.
    *   **Missing:** We do **not** store the full HTTP response payload (logprobs, headers, tool_calls) in the DB.
5.  **Token Accounting (/solve):**
    *   **Answer:** **UsageLog Only.**
    *   **Details:** `/solve` writes to `UsageLog` (via `record_request_event` and `UsageLog` at line 4163).
    *   **LlmUsageLedger:** This table is **NOT** written to by the `/solve` endpoint. It is currently used **only** by `FollowupChatTurn`.

## C) Schema System Details

6.  **Top 10 JSON Schemas:**
    *   **Source:** `backend/app/schemas/na_math_solver_v3.py`.
    *   **Primary Schema:** `math_solver_response` (Derived from `SolveResponseV3`).
    *   **Strict Mode:** **Enabled** (`"strict": True`).
    *   **Key Entries:** `solve_response_v3`, `plot_trigger_response`, `plot_spec_response`.
7.  **Schema Failure Handling:**
    *   **Code Path:** `solver_v3.py` -> `_check_status_and_validate`.
    *   **Mechanism:**
        1.  Checks OpenAI status (`incomplete`, `length`).
        2.  Validates against JSON Schema using `Draft202012Validator`.
        3.  **Repair Loop:** If validation fails, `_repair_response` is called (1-shot) with the error list to ask the LLM to fix it.
    *   **Persistence:** Failed attempts are **not** saved to DB if the repair also fails (raises 500).

## D) CanonicalProblem/CIR Readiness

8.  **CIR Fields:**
    *   **Table:** `CanonicalProblem`.
    *   **Fields:**
        *   `intent` (String, default `"unknown"`).
        *   `normalized_text` (String).
        *   `normalized_problem_hash` (String, SHA256).
    *   **Readiness:** Low. `intent` is just a string, not a structured classification (e.g., "PLOT_REQUIRED", "EXEC_REQUIRED").
9.  **Intermediate Expressions:**
    *   **Answer:** **Not Stored.**
    *   `SolveSession` stores `solution_steps_text` as a single blob string. We do *not* store individual step-by-step LaTeX expressions in a queryable format.

## E) Execution Safety & Architecture

10. **Python Sandbox:**
    *   **Status:** **Non-Existent.**
    *   **Findings:** There is no Docker/Subprocess execution code in the codebase specific to running user/LLM code. `safe_parser.py` explicitly *avoids* `eval()`/`exec()` to be safe.
11. **Observability:**
    *   **Errors:** Captured in `RequestEvent` (status=`error`) and written to `/app/storage/solve_debug.log`.
    *   **Trace IDs:** `request_id` exists in `RequestEvent`, but we do **not** have per-attempt row granularity in the DB (since `SolverOutputAttempt` is unused).

## F) ERD Confirmation

12. **Active Runtime Tables (Confirmed via Code Usage):**

| Table | Write Status | Notes |
| :--- | :--- | :--- |
| `User` | **Read/Write** | - |
| `ChatSession` | **Write** | Created per solve. |
| `ChatMessage` | **Write** | Stores inputs/outputs. |
| `SolveSession` | **Write** | Immutable snapshot. |
| `CanonicalProblem` | **Write** | Deduplication. |
| `UsageLog` | **Write** | /solve accounting. |
| `LlmUsageLedger` | **Write (Followup Only)** | **Gap:** Not used by /solve. |
| `SolverOutputAttempt` | **Unused** | Defined but never written. |
