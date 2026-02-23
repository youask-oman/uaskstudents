# Plot Engine Contract

## Supported Recipe Patterns
- `series[].kind = function`: continuous `y=f(x)`
- `series[].kind = sequence`: discrete terms or partial sums on integer index
- `series[].kind = parametric`: `(x(t), y(t))`
- `series[].kind = implicit`: `F(x,y)=0` contour
- `points[]`: scatter points + labels
- `annotations[]`: `hline` and `vline`
- Legacy `expressions[]` with `for n=..` and `cumsum(...)` is normalized into `series[]`

## Classification Rules
- `DISCRETE_SEQUENCE`: any of `for n=`, `cumsum(`, `a_n`, `S_N`, `vs N`
- `PARAMETRIC`: `x(t)`/`y(t)` hints
- `CATEGORICAL_HIST`: histogram/bar hints
- default: `CONTINUOUS_FUNCTION`

## Sampling Defaults
- Discrete sequence: integer grid `n = arange(n_min, n_max+1)`
- Continuous function: `linspace(x_min, x_max, 500)`
- Parametric: `linspace(t_min, t_max, 1000)`
- Implicit: bounded contour grid up to `450x450`

## Safety and Numerical Guards
- Complex outputs:
  - if `max(|imag|) <= 1e-10`: cast to real
  - else fail series with `complex_output`
- NaN/Inf:
  - continuous: discontinuity masking
  - discrete: fail series if all invalid
- No silent blank plots: fallback panel is rendered with diagnostics

## Autoscaling
- If `y_domain` missing or null:
  - infer from finite rendered series values
  - 5% padding (or 1.0 if flat)
  - fallback to `[-1,1]` only when no finite values exist

## Error Codes / Diagnostics (warnings/errors)
- `series_i:...` parse/eval failures
- `sequence:nan_only`
- `function:nan_only`
- `...:complex_output`
- `normalized_expressions_to_series`
- `normalized_key_point_placeholder_to_hline`
- `fallback_plot_rendered`

## Telemetry Fields
- `classification`
- `normalized_recipe`
- `sampling`
- `warnings`
- `errors`
- `fallback_used`

## Before/After Examples
1. Alternating sequence (`(-1)^(n+1)/n^2`, `n=1..200`):
Before: float `linspace` + complex artifacts -> blank
After: integer grid + safe sequence eval -> rendered

2. Partial sum (`cumsum(...)`):
Before: expression not executable as series
After: normalized to `sequence_kind=partial_sum` and plotted

3. Placeholder key point (`x="N_range"`):
Before: invalid x skipped
After: converted to `hline(y=...)`

4. Missing y-domain:
Before: wide defaults (often unreadable)
After: finite autoscale from rendered data

5. Broken series expression:
Before: empty chart
After: fallback message + diagnostics
