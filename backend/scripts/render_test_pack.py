from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List

import requests


BASE_URL = "http://localhost:9000"
OUT_DIR = Path(__file__).resolve().parents[1] / "reports" / "evidence" / "math_render"


def build_formula_pack() -> List[Dict[str, Any]]:
    basics = [
        r"\frac{a}{b}",
        r"\sqrt{x^2+1}",
        r"\sum_{k=1}^{n} k",
        r"\int_0^1 x^2\,dx",
        r"\lim_{x\to 0}\frac{\sin x}{x}",
        r"\begin{pmatrix}1&2\\3&4\end{pmatrix}",
        r"\begin{cases}x^2,&x\ge 0\\-x,&x<0\end{cases}",
        r"\log(x^2+1)",
        r"\frac{d}{dx}(x^3)=3x^2",
        r"\RR = \mathbb{R}",
    ]
    items: List[Dict[str, Any]] = []
    for idx in range(12):
        for f in basics:
            items.append(
                {
                    "latex": f,
                    "display_mode": idx % 2 == 0,
                    "macros": {"\\RR": "\\mathbb{R}"},
                    "scale": 1.0,
                }
            )
    # invalid formulas for never-break checks
    items.extend(
        [
            {"latex": r"\frac{", "display_mode": False, "macros": {}, "scale": 1.0},
            {"latex": r"\begin{pmatrix}1&2", "display_mode": True, "macros": {}, "scale": 1.0},
            {"latex": r"\unknowncommand{abc}", "display_mode": False, "macros": {}, "scale": 1.0},
        ]
    )
    return items


def post_render(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    started = time.perf_counter()
    resp = requests.post(
        f"{BASE_URL}/api/v1/math/render",
        json={
            "items": items,
            "options": {"font": "tex", "sanitize": True, "return_metrics": True},
        },
        timeout=300,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    payload = resp.json() if resp.content else {}
    payload["_http_status"] = resp.status_code
    payload["_roundtrip_ms"] = latency_ms
    return payload


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    items = build_formula_pack()

    first = post_render(items)
    second = post_render(items)

    (OUT_DIR / "render_pack_request.json").write_text(json.dumps({"items": items}, indent=2), encoding="utf-8")
    (OUT_DIR / "render_pack_first.json").write_text(json.dumps(first, indent=2), encoding="utf-8")
    (OUT_DIR / "render_pack_second.json").write_text(json.dumps(second, indent=2), encoding="utf-8")

    first_results = first.get("results") if isinstance(first.get("results"), list) else []
    ok_count = sum(1 for x in first_results if isinstance(x, dict) and x.get("ok"))
    err_count = len(first_results) - ok_count
    svgs = [x.get("svg", "") for x in first_results if isinstance(x, dict) and x.get("ok")]
    snippets = [s[:300] for s in svgs[:3]]
    (OUT_DIR / "sample_svg_snippets.txt").write_text("\n\n---\n\n".join(snippets), encoding="utf-8")

    second_stats = second.get("stats") if isinstance(second.get("stats"), dict) else {}
    first_stats = first.get("stats") if isinstance(first.get("stats"), dict) else {}

    all_latencies = []
    for run in (first, second):
        for item in (run.get("results") if isinstance(run.get("results"), list) else []):
            if isinstance(item, dict) and isinstance(item.get("metrics"), dict):
                d = item["metrics"].get("duration_ms")
                if isinstance(d, (int, float)):
                    all_latencies.append(float(d))

    summary = {
        "requested": len(items),
        "first": {
            "http_status": first.get("_http_status"),
            "ok": ok_count,
            "error": err_count,
            "cache_hits": first_stats.get("cache_hits"),
            "rendered": first_stats.get("rendered"),
            "latency_ms": first_stats.get("latency_ms"),
            "roundtrip_ms": first.get("_roundtrip_ms"),
        },
        "second": {
            "http_status": second.get("_http_status"),
            "cache_hits": second_stats.get("cache_hits"),
            "rendered": second_stats.get("rendered"),
            "latency_ms": second_stats.get("latency_ms"),
            "roundtrip_ms": second.get("_roundtrip_ms"),
        },
        "perf": {
            "p50_item_ms": statistics.median(all_latencies) if all_latencies else None,
            "p95_item_ms": statistics.quantiles(all_latencies, n=20)[18] if len(all_latencies) >= 20 else None,
        },
    }
    (OUT_DIR / "render_pack_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

