# Dead Code / Config / Dependency Audit

Date: 2026-02-20
Status: Phase 2 complete (HIGH-confidence removals only)

## Scope and Safety Constraints
- No runtime-behavior changes intended.
- No migration/secrets/deployment-critical deletions.
- Only HIGH-confidence items removed in this phase.

## Entrypoints / Execution Paths (confirmed)
- Frontend: Next app router in `src/app/**` with API routes in `src/app/api/**/route.ts`.
- Backend: FastAPI app at `backend/app/main.py`; Celery worker at `backend/app/worker.py`.
- Docker startup surfaces:
  - `docker-compose.yml`
  - `docker-compose.dev.yml`
  - `backend/Dockerfile`
- CI workflows: none found in repo `.github/workflows`.
- Makefile: none found.

## Baseline (before removals)
Commands run:
1. `npm install` => PASS
2. `npm run lint` => FAIL
3. `npm run typecheck` => PASS
4. `npx jest --ci` => FAIL
5. `npm run build` => PASS
6. `python -m pytest -q` (in `backend/`) => FAIL
7. `docker compose -f docker-compose.yml up -d postgres redis orchestrator` => PASS
8. `GET http://localhost:9000/health` => PASS
9. `docker compose -f docker-compose.yml down` => PASS

## Phase 2 changes applied (HIGH-confidence only)

### Deleted dependencies
Removed from `package.json` + lockfile:
- `clsx`
- `date-fns`
- `file-saver`
- `tailwind-merge`
- `@types/file-saver`
- `baileys`

Command:
- `npm uninstall clsx date-fns file-saver tailwind-merge @types/file-saver baileys`

### Deleted file
- `backend/app/services/vision copy.py`

Reason:
- No static references/imports found; duplicate backup-style file name.

## Post-change gate results (after removals)
Commands rerun:
1. `npm install` => PASS
2. `npm run lint` => FAIL
- Same known hard blockers remain:
  - `react-hooks/preserve-manual-memoization` in `src/components/math-canvas/SolutionStepsBlock.tsx`
  - `@typescript-eslint/no-require-imports` in `tmp_mq_test/multiQuestionDetector.js`
3. `npm run typecheck` => PASS
4. `npx jest --ci` => FAIL
- Existing failures remain (Playwright specs run under Jest; missing `vitest` in `static_design/multiQuestionDetector.test.ts`).
- Additional surfaced failure: ESM parse issue on `react-markdown` in current Jest transform setup.
5. `npm run build` => PASS
6. `python -m pytest -q` (in `backend/`) => FAIL
- Same collection/import failures as baseline (9 errors).
7. `docker compose -f docker-compose.yml up -d postgres redis orchestrator` => PASS
8. `GET http://localhost:9000/health` => PASS (first attempt transient receive close, second attempt PASS)
9. `docker compose -f docker-compose.yml down` => PASS

## What was NOT removed and why
- `watchtower` compose service: no strong in-repo usage evidence, but could be ops-managed externally. Marked `NEEDS_CONFIRMATION`.
- `static_design/multiQuestionDetector.test.ts`: looks legacy and currently problematic, but retained as MED confidence pending confirmation.
- scripts with low evidence (`start:e2e`, `validate:templates`, `test:e2e`, `e2e`, `qa:frontend-regression`): possible manual workflows.
- compose env vars with no in-repo reads (`PIX2TEXT_HOME`, `YOLO_RUNS_DIR`, `RUNS_DIR`, `WATCHTOWER_*`): may be runtime-consumed by external tools/libraries.

## Current candidate status
- HIGH removed: yes (6 deps + 1 file).
- Remaining candidates are MED/LOW confidence and require confirmation/deprecation strategy.

## Rollback instructions
- Revert this phase cleanly:
  - `git restore package.json package-lock.json`
  - `git restore "backend/app/services/vision copy.py"`
  - or `git revert <phase2-commit>` if committed.
