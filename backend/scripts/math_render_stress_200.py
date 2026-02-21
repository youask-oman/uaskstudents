from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi.testclient import TestClient


def _hard_equations() -> List[str]:
    seed: List[str] = [
        r"\frac{-b\pm\sqrt{b^2-4ac}}{2a}",
        r"\int_0^\infty e^{-x^2}\,dx=\frac{\sqrt{\pi}}{2}",
        r"\sum_{n=1}^{\infty}\frac{1}{n^2}=\frac{\pi^2}{6}",
        r"\lim_{x\to 0}\frac{\sin x}{x}=1",
        r"\begin{bmatrix}a&b\\c&d\end{bmatrix}\begin{bmatrix}x\\y\end{bmatrix}=\begin{bmatrix}e\\f\end{bmatrix}",
        r"\det\begin{pmatrix}1&2&3\\0&1&4\\5&6&0\end{pmatrix}",
        r"\left|\frac{z_1-z_2}{1-\overline{z_2}z_1}\right|",
        r"\forall \epsilon>0\ \exists \delta>0:\ |x-a|<\delta\Rightarrow |f(x)-L|<\epsilon",
        r"\nabla\cdot\vec{E}=\frac{\rho}{\varepsilon_0}",
        r"\nabla\times\vec{B}=\mu_0\vec{J}+\mu_0\varepsilon_0\frac{\partial\vec{E}}{\partial t}",
        r"\oint_{\partial\Omega}\vec{F}\cdot d\vec{r}=\iint_{\Omega}(\nabla\times\vec{F})\cdot\hat{n}\,dA",
        r"\iiint_V \rho(x,y,z)\,dV",
        r"\left(\sum_{k=1}^n k\right)^2=\sum_{k=1}^n k^3",
        r"\operatorname{Var}(X)=\mathbb{E}[X^2]-\mathbb{E}[X]^2",
        r"\mathbb{P}(A\mid B)=\frac{\mathbb{P}(A\cap B)}{\mathbb{P}(B)}",
        r"\operatorname{rank}(A)=\dim(\operatorname{Col}(A))",
        r"\ker(T)=\{v\in V:T(v)=0\}",
        r"\left\lfloor\frac{n}{2}\right\rfloor+\left\lceil\frac{n}{2}\right\rceil=n",
        r"\binom{n}{k}=\frac{n!}{k!(n-k)!}",
        r"\prod_{i=1}^n (1+x_i)",
        r"\left[\begin{array}{ccc|c}1&2&-1&0\\0&1&3&5\\2&-1&1&4\end{array}\right]",
        r"\begin{cases}x+y=1\\x-y=3\end{cases}",
        r"\begin{aligned}f(x)&=x^3-6x^2+11x-6\\f'(x)&=3x^2-12x+11\end{aligned}",
        r"\left(\frac{d}{dx}\right)^n x^m=\frac{m!}{(m-n)!}x^{m-n}",
        r"\int_a^b f'(x)g(x)\,dx=[f(x)g(x)]_a^b-\int_a^b f(x)g'(x)\,dx",
    ]
    out: List[str] = []
    out.extend(seed)

    for n in range(2, 42):
        out.append(rf"\sum_{{k=1}}^{{{n}}}\frac{{(-1)^k}}{{k}}")
        out.append(rf"\int_0^1 x^{{{n}}}(1-x)^{{{n-1}}}\,dx")
        out.append(rf"\left(1+\frac{{1}}{{{n}}}\right)^{{{n}}}")
        out.append(rf"\frac{{d^{{{n%5+1}}}}}{{dx^{{{n%5+1}}}}}\left(x^{{{n+3}}}\sin x\right)")
        out.append(rf"\begin{{pmatrix}}1&{n}\\{n+1}&{n+2}\end{{pmatrix}}^{{-1}}")

    for a in range(1, 31):
        out.append(rf"\lim_{{x\to {a}}}\frac{{x^2-{a**2}}}{{x-{a}}}")
        out.append(rf"\int_{{-{a}}}^{{{a}}}\cos({a}x)\,dx")
        out.append(rf"\sqrt[{(a%4)+2}]{{\frac{{{a}x^{{{(a%5)+2}}}}}{{1+x^2}}}}")

    # Deduplicate while preserving order.
    dedup: List[str] = []
    seen = set()
    for eq in out:
        if eq in seen:
            continue
        seen.add(eq)
        dedup.append(eq)
    return dedup[:220]


def run() -> Dict[str, Any]:
    from app.main import app

    equations = _hard_equations()
    with TestClient(app) as client:
        results: List[Dict[str, Any]] = []
        batch_size = 25
        for i in range(0, len(equations), batch_size):
            chunk = equations[i : i + batch_size]
            payload = {
                "items": [
                    {"latex": eq, "display_mode": True, "macros": {}, "scale": 1.0}
                    for eq in chunk
                ],
                "options": {"font": "tex", "sanitize": True, "return_metrics": True},
            }
            resp = client.post("/api/v1/math/render", json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"math/render failed status={resp.status_code} body={resp.text[:500]}")
            body = resp.json()
            chunk_results = body.get("results") or []
            for j, row in enumerate(chunk_results):
                eq = chunk[j] if j < len(chunk) else ""
                results.append(
                    {
                        "latex": eq,
                        "ok": bool(row.get("ok")),
                        "error": (row.get("error") or {}).get("code") if isinstance(row, dict) else "unknown",
                        "key": row.get("key") if isinstance(row, dict) else None,
                    }
                )

    failures = [r for r in results if not r["ok"]]
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "passed": len(results) - len(failures),
        "failed": len(failures),
        "failures": failures[:50],
    }


if __name__ == "__main__":
    here = Path(__file__).resolve()
    backend_dir = here.parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    report = run()
    out_dir = Path("reports/math_render_stress")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "math_render_stress_220.json"
    txt_path = out_dir / "math_render_stress_220.txt"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    txt_path.write_text(
        (
            f"Math render stress report\n"
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
