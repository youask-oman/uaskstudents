# Admin Dashboard Capability Audit Report

Generated on: 2026-02-25

## Scope
- Frontend admin navigation and route inventory under `src/app/admin/*`
- Admin API proxy routes under `src/app/api/admin/*`
- Backend admin endpoints under `/api/admin/*` and `/api/v1/admin/*` via existing manifest API checks

## Backend Capability Groups Mapped
- Core admin analytics/users/quotas: `/api/v1/admin/*`
- Prompt + schema + bindings: `/api/v1/admin/prompt-registry/*`, `/api/v1/admin/prompt_bindings*`
- OCR and content admin: `/api/admin/ocr-configuration*`, `/api/admin/content/*`
- Billing and credits: `/api/admin/billing/*`, `/api/v1/admin/credits/*`
- WhatsApp control + abuse ops: `/api/admin/whatsapp/*`
- Legal management/public legal read: `/api/legal/*`, admin edit routes under `/admin/legal/*` UI

## Required Questions

### 1) What admin routes existed but were not in navigation?
Routes found and fixed by adding nav entries:
- `/admin/whatsapp-abuse`
- `/admin/subscriptions`
- `/admin/billing/packs`
- `/admin/billing/pricing`
- `/admin/legal/terms`
- `/admin/legal/privacy`

Routes intentionally excluded (documented in matrix):
- `/admin/users/[id]` (detail page via `/admin/users`)
- `/admin/billing/users/[userId]/wallet` (detail page via billing links)
- `/admin/billing/programs/enrollments` (secondary detail route; primary is `/admin/billing/enrollments`)
- `/admin/billing/legacy` (legacy compatibility)
- `/admin/legacy/payments` (deprecated)
- `/admin/legacy/plans` (deprecated)
- `/admin/legacy/subscriptions` (deprecated)

### 2) Which tabs were inaccessible to admin and why (RBAC vs flags vs broken routing)?
No missing-route tabs remain in active admin navigation after this pass.

Known role-restricted behavior (documented):
- `/admin/billing/topup-products`: superadmin for mutations, admin read-only
- `/admin/billing/refunds`: admin+ with elevated operations for sensitive actions

No frontend feature-flag-based tab hiding is currently enforced in admin manifest.

### 3) What is the final, authoritative list of admin capabilities?
Authoritative source:
- `docs/admin_capability_matrix.md`
- `docs/admin_capability_matrix.json`

These are generated from:
- `admin_nav_manifest.json` (UI nav source)
- `src/app/admin/**/page.tsx` (registered admin routes)
- documented exclusion list in audit script

### 4) What prevents someone from adding a new admin route and forgetting to add it to navigation?
Automated guardrails now in place:
- `scripts/admin_capability_audit.mjs --check`
  - fails if a route exists but is missing in nav and not explicitly excluded
  - fails if nav points to a non-existent route
  - fails if generated matrix is out of date
- npm script: `npm run admin:capabilities:check`
- E2E tab traversal: `tests/e2e/admin_nav_full_access.spec.ts`
  - logs in as admin
  - opens every admin nav tab
  - verifies page intro header and absence of access-denied state

## Additional Changes
- Added universal admin page intro header via layout:
  - `src/components/admin/AdminPageIntro.tsx`
  - wired in `src/app/admin/layout.tsx`
- This enforces top-of-page purpose/actions guidance consistently for all admin pages.
