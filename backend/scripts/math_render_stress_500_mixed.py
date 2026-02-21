from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi.testclient import TestClient


def _mixed_long_university_cases() -> List[str]:
    cases: List[str] = []

    seeds = [
        r"\text{Given the functional equation, evaluate } \int_0^\infty \frac{x^{a-1}}{1+x}\,dx \text{ and conclude } \pi\csc(\pi a) \text{ for } 0<a<1.",
        r"\text{In linear algebra, if } A\in\mathbb{R}^{n\times n} \text{ is diagonalizable, then } A=PDP^{-1} \text{ and therefore } A^k=PD^kP^{-1}.",
        r"\text{For optimization, define } \mathcal{L}(x,\lambda)=f(x)+\lambda^\top g(x) \text{ and enforce } \nabla_x\mathcal{L}=0,\, g(x)=0.",
        r"\text{Using Fourier analysis, write } f(x)=\sum_{k=-\infty}^{\infty}\hat f_k e^{ikx} \text{ with } \hat f_k=\frac{1}{2\pi}\int_{-\pi}^{\pi} f(x)e^{-ikx}dx.",
        r"\text{For PDE boundary data, solve } u_t-\alpha u_{xx}=0 \text{ with } u(0,t)=u(L,t)=0 \text{ and } u(x,0)=\phi(x).",
    ]
    cases.extend(seeds)

    for n in range(2, 252):
        k = (n % 7) + 2
        p = (n % 5) + 3
        q = (n % 9) + 4
        cases.append(
            rf"\text{{Problem {n}: compute and simplify }} "
            rf"\sum_{{j=1}}^{{{n}}}\frac{{(-1)^j}}{{j^{k}}} "
            rf"\text{{ while tracking error }} \left|R_{{{n}}}\right|<\frac{{1}}{{{n}^{k-1}}}."
        )
        cases.append(
            rf"\text{{For the model with parameter }} \theta_{{{n}}},\ "
            rf"\nabla_\theta J(\theta)=\frac{{1}}{{m}}\sum_{{i=1}}^m "
            rf"\left(h_\theta(x_i)-y_i\right)x_i + \lambda\theta "
            rf"\text{{ and set }} \nabla_\theta J(\theta)=0."
        )
        cases.append(
            rf"\text{{Show that }} \int_0^1 x^{{{p}}}(1-x)^{{{q}}}\,dx="
            rf"\frac{{\Gamma({p+1})\Gamma({q+1})}}{{\Gamma({p+q+2})}} "
            rf"\text{{ and compare with }} B({p+1},{q+1})."
        )
        cases.append(
            rf"\text{{Consider }} f_{{{n}}}(x)=x^{{{k}}}e^{{-x}} \text{{ then }} "
            rf"\frac{{d^2}}{{dx^2}}f_{{{n}}}(x)=e^{{-x}}\left(x^{{{k}}}-2{k}x^{{{k-1}}}+{k}({k-1})x^{{{k-2}}}\right)."
        )
        cases.append(
            rf"\text{{Given matrix }} A_{{{n}}}=\begin{{pmatrix}}{k}&{p}&1\\0&{q}&2\\0&0&{n+3}\end{{pmatrix}}, "
            rf"\text{{ compute }} \det(A_{{{n}}})={k*q*(n+3)} \text{{ and verify eigenvalues on the diagonal.}}"
        )
        cases.append(
            rf"\text{{In probability, }} \mathbb{{P}}(X\ge t)\le e^{{-\lambda t}}\mathbb{{E}}[e^{{\lambda X}}], "
            rf"\text{{ then optimize over }} \lambda>0 \text{{ for case }} t={n}."
        )
        cases.append(
            rf"\text{{Use series expansion: }} \log(1+x)=\sum_{{r=1}}^\infty (-1)^{{r+1}}\frac{{x^r}}{{r}},\ |x|<1, "
            rf"\text{{ and substitute }} x=\frac{{1}}{{{n+2}}}."
        )
        cases.append(
            rf"\text{{With constraints }} x^2+y^2={n+5},\ xy={k}, "
            rf"\text{{ derive }} (x+y)^2={n+5+2*k} \text{{ and }} (x-y)^2={n+5-2*k}."
        )

    # Keep order stable and unique.
    unique: List[str] = []
    seen = set()
    for item in cases:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique[:500]


def run() -> Dict[str, Any]:
    from app.main import app

    items = _mixed_long_university_cases()
    with TestClient(app) as client:
        results: List[Dict[str, Any]] = []
        batch_size = 25
        for i in range(0, len(items), batch_size):
            chunk = items[i : i + batch_size]
            payload = {
                "items": [
                    {"latex": latex, "display_mode": True, "macros": {}, "scale": 1.0}
                    for latex in chunk
                ],
                "options": {"font": "tex", "sanitize": True, "return_metrics": True},
            }
            resp = client.post("/api/v1/math/render", json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"math/render failed status={resp.status_code} body={resp.text[:600]}")
            body = resp.json()
            chunk_results = body.get("results") or []
            for j, row in enumerate(chunk_results):
                latex = chunk[j] if j < len(chunk) else ""
                results.append(
                    {
                        "latex": latex,
                        "ok": bool(row.get("ok")),
                        "error": (row.get("error") or {}).get("code") if isinstance(row, dict) else "unknown",
                        "message": (row.get("error") or {}).get("message") if isinstance(row, dict) else None,
                        "key": row.get("key") if isinstance(row, dict) else None,
                    }
                )

    failures = [r for r in results if not r["ok"]]
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "suite": "math_render_stress_500_mixed_words",
        "total": len(results),
        "passed": len(results) - len(failures),
        "failed": len(failures),
        "failures": failures[:100],
    }


if __name__ == "__main__":
    here = Path(__file__).resolve()
    backend_dir = here.parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    report = run()
    out_dir = Path("reports/math_render_stress")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "math_render_stress_500_mixed.json"
    txt_path = out_dir / "math_render_stress_500_mixed.txt"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    txt_path.write_text(
        (
            "Math render stress report (500 mixed long text+math)\n"
            f"timestamp_utc: {report['timestamp_utc']}\n"
            f"total: {report['total']}\n"
            f"passed: {report['passed']}\n"
            f"failed: {report['failed']}\n"
        ),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    if int(report.get("failed") or 0) > 0:
        raise SystemExit(1)
