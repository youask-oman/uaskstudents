# Tier Output Analysis and Optimization Plan

Generated: 2026-02-14
Source artifacts: `reports/tier_live_runs/*_openai_visits.json`, `reports/tier_live_runs/*_sse.json`, `reports/tier_live_runs/FULL_OPENAI_TIER_REPORT.md`

## 1) Observed Differences Across Final Outputs

### 1.1 Call count and token cost (current run)
- FREE: 3 visits = `solve_main` + `solve_json_repair` + `plot_spec`
- SHORT: 4 visits = `solve_main` + `solve_json_repair` + `plot_trigger` + `plot_spec`
- STANDARD: 3 visits = `solve_main` + `solve_json_repair` + `plot_spec`
- RESEARCH: 3 visits = `solve_main` + `solve_json_repair` + `plot_spec`

Aggregate totals from artifacts:
- Total visits: `13`
- Main-call tokens: `24,186`
- Repair-call tokens: `24,186` (near 1:1 duplicate spend)
- Plot-related LLM calls: `5` (all failed in this run due max_tokens incompatibility)

### 1.2 Structural output differences by tier (from parsed repair outputs)
- FREE:
  - `refusal.is_refusal=true`
  - `steps=0`
  - final answer collapsed to error text
- SHORT:
  - `steps=2`
  - concise final answer
  - minimal mistakes array
- STANDARD:
  - `steps=6`
  - richer checks/rules and visualization recipe
- RESEARCH:
  - `steps=10`
  - most detailed reasoning and strongest quality metadata

### 1.3 Quality/risk differences seen in outputs
- FREE output degraded because main output was truncated and repair inherited broken payload context.
- SHORT output had better compactness but still required repair pass.
- STANDARD/RESEARCH generally solved correctly but still paid full second call.
- Detected enum/schema normalization issues existed in earlier runs (mapped values not matching schema enums), which triggered avoidable repair.

## 2) Why Calls Are Wasted

### 2.1 Repair call almost duplicates full generation
- In this run, repair token usage ~= main token usage for all tiers.
- This indicates the repair prompt path is effectively a second full solve, not a lightweight patch.

### 2.2 Plot LLM path was pure overhead
- Plot trigger/spec calls added 1-2 visits per request and failed (`max_tokens` mismatch for chat completions).
- Deterministic backend plot generation already existed as fallback and is sufficient for math function plotting.

### 2.3 Prompt duplication inflates input tokens
- Request traces show very large instruction blocks in both system and developer roles.
- If identical or near-identical, this doubles instruction tokens with no quality gain.

## 3) Why Plot Spec LLM Is Not Needed

For your use case (math solve + graphing), deterministic plotting is better because:
- Inputs already provide expression + range + key points.
- Backend can evaluate safely via SymPy/numpy and render deterministically.
- No hallucinated plot schema, no extra LLM latency/cost, reproducible output.
- Better incident profile (fewer external dependencies in the critical path).

LLM plot spec is only useful for ambiguous visualization intent (rare in solve flow) and can remain optional/offline.

## 4) Implemented Production Changes (this pass)

### 4.1 Removed OpenAI plot dependency in solve path
- `backend/app/services/plot_integration.py`
- Deterministic-only plot generation path is used.
- No plot trigger/spec OpenAI call is required.

### 4.2 Hardened deterministic plot generation
- `backend/app/services/plot_integration.py`
- Plot builder now reads canonical `visuals.plots[0].recipe` and `domain` when present.
- Uses safe parser + numpy sampling to generate Plotly-compatible line data.
- Preserves and overlays key points as marker trace.
- Falls back to extracting expression/range from problem text when recipe is missing.

### 4.3 Reduced redundant prompt tokens
- `backend/app/services/solver_v3.py`
- Added message builder that deduplicates developer prompt when it is semantically identical to system prompt.

### 4.4 Reduced forced repair overhead (prior patch retained)
- Repair prompt no longer embeds full schema blob.
- Repair payload clips oversized invalid JSON context.
- Second repair pass disabled by default unless explicitly enabled by env var.

### 4.5 Enum normalization fixes (prior patch retained)
- `backend/app/services/response_mapper.py`
- Domain/grade/difficulty/task normalization aligned to schema enums to prevent avoidable validation failures.

## 5) How to Reduce OpenAI Calls Further

### Priority A (largest impact)
1. Keep single solve call as default.
2. Run repair only if strict parse/validation fails and response is not recoverable by local canonicalizer.
3. Keep second repair pass OFF by default in production.

Expected effect:
- Average visits can drop from 3-4 to ~1-2.
- Major token savings from removing near-duplicate repair calls.

### Priority B
1. Keep LLM plotting disabled in solve request path.
2. Use deterministic plotting from recipe/expression only.

Expected effect:
- Remove 1-2 LLM visits per request where plot is on.

### Priority C
1. Continue prompt dedup to avoid duplicated instruction payloads.
2. Move stable global constraints into one compact system prompt.
3. Keep developer prompt tier-specific and short.

Expected effect:
- Lower input tokens every request without model behavior loss.

## 6) Prompt Improvement Recommendations (low-token, high-accuracy)

### 6.1 Keep a strict two-part contract
- System prompt: stable safety/output contract only.
- Developer prompt: tier behavior + output priorities only.

### 6.2 Remove repeated directives
- Avoid repeating schema-mode and anti-empty rules in both system and developer blocks.
- Keep one canonical instruction for each policy.

### 6.3 Use compact deterministic wording
- Prefer rule bullets with explicit caps (`steps<=N`, `math_latex<=M`) over long prose examples.

### 6.4 Clarification/verification policy
- In prompt, explicitly state:
  - backend is source of truth for verification,
  - model should provide candidate solutions, not verified claims.
- This reduces contradictory fields and repair triggers.

## 7) Schema Improvement Recommendations

### 7.1 Tier schemas should be tighter and smaller
- SHORT/FREE schemas should not include large optional blocks that are never used.
- Fewer optional branches => fewer malformed outputs.

### 7.2 Keep enums narrow and shared
- Centralize enum vocab used by model and mapper.
- Avoid alias proliferation in prompt text; map aliases in backend only.

### 7.3 Reduce nullable clutter where possible
- Excess nullable fields increase invalid combinations and output drift.
- Make non-essential fields optional instead of required-null.

### 7.4 Plot schema strategy
- Keep LLM output schema at recipe-level only (expr/domain/sampling/key_points).
- Never ask model for raw arrays.
- Rendering schema should remain internal/backend-only.

## 8) Proposed Next Validation Run

After current code changes, run one 4-tier live test with `graph_mode=on` and confirm:
1. No OpenAI `plot_trigger`/`plot_spec` calls in artifacts.
2. Reduced total visit count and lower token spend.
3. FREE no longer degrades to refusal due truncation/repair loops.
4. Deterministic plot uses model recipe range (e.g., `[-3,3]`) and key points.

---

This report focuses on the exact artifacts in `reports/tier_live_runs` and aligns with production objective: better math quality with fewer calls/tokens.
