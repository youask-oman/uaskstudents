# Snap & Solve Isolation Fence

This folder is **Snap & Solve only**.

## Forbidden To Modify (for this feature)

- `src/app/solve/page.tsx` Text tab logic/content blocks (except Snap tab wiring only)
- `src/app/solve/page.tsx` Voice tab logic/content blocks
- `src/components/MathInput.tsx`
- `src/components/InputModeSelector.tsx`
- `src/components/LiveMathPreview.tsx`
- `src/components/workspace/*`
- `src/components/math/*`
- `src/components/snap/*` (legacy Snap flow components)
- `src/app/globals.css`
- Any Text/Voice routes or API handlers

## Allowed

- New Snap components under `src/components/snap_solve/*`
- Snap-only backend endpoint(s)
- Snap-only tests
