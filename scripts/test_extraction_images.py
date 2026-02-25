from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.math_extract_pipeline import run_math_extraction_pipeline


@dataclass
class FixtureCase:
    role: str
    path: Path
    source_type: str
    max_pages: int = 5


def _default_cases(root: Path) -> List[FixtureCase]:
    return [
        FixtureCase("graph_multi_curve", root / "Screenshot 2026-01-28 093055.jpg", "image"),
        FixtureCase("sat_graph_mcq", root / "Screenshot 2026-02-19 193031.jpg", "image"),
        FixtureCase("table_question", root / "EOCP-Math-Test-Questions.pdf", "pdf", max_pages=5),
        FixtureCase("geometry_silo", root / "Screenshot 2026-02-19 193002.jpg", "image"),
        FixtureCase("graph_parameter_k", root / "Screenshot 2026-02-19 193310.jpg", "image"),
    ]


def _assert_case(case: FixtureCase, extraction_json: Dict[str, Any]) -> List[str]:
    errs: List[str] = []
    detected = extraction_json.get("detected") or {}
    raw = extraction_json.get("raw") or {}
    if not str(raw.get("transcription") or "").strip():
        errs.append("raw.transcription is empty")

    if case.role in {"graph_multi_curve", "sat_graph_mcq", "graph_parameter_k"}:
        graph = extraction_json.get("graph") or {}
        if not detected.get("has_graph"):
            errs.append("has_graph=false")
        if not any(
            [
                graph.get("x_label"),
                graph.get("y_label"),
                graph.get("x_ticks"),
                graph.get("y_ticks"),
                graph.get("legend"),
            ]
        ):
            errs.append("graph metadata missing (axes/ticks/legend)")

    if case.role == "sat_graph_mcq":
        mcq = extraction_json.get("mcq") or {}
        choices = mcq.get("choices") or {}
        if not detected.get("has_mcq"):
            errs.append("has_mcq=false")
        if len(choices) < 4:
            errs.append("mcq choices incomplete")

    if case.role == "table_question":
        table = extraction_json.get("table") or {}
        if not detected.get("has_table"):
            errs.append("has_table=false")
        if not str(table.get("markdown") or "").strip():
            errs.append("table.markdown empty")
        if not str(table.get("csv") or "").strip():
            errs.append("table.csv empty")

    if case.role == "geometry_silo":
        geom = extraction_json.get("geometry") or {}
        dims = geom.get("dimensions") or []
        if not detected.get("has_geometry"):
            errs.append("has_geometry=false")
        if not dims:
            errs.append("geometry.dimensions empty")

    return errs


async def _run_case(case: FixtureCase, out_dir: Path) -> Tuple[FixtureCase, Dict[str, Any], List[str]]:
    content = case.path.read_bytes()
    request_id = f"extract-{case.role}-{int(datetime.utcnow().timestamp())}"
    result = await run_math_extraction_pipeline(
        request_id=request_id,
        source_type=case.source_type,
        filename=case.path.name,
        content_bytes=content,
        max_pages=case.max_pages,
        keep_rendered_pages=True,
    )

    extraction = result.get("extraction") or {}
    structured = extraction.get("json") or {}
    if case.source_type == "pdf":
        structured = (structured.get("merged") if isinstance(structured, dict) else None) or {}

    case_dir = out_dir / case.role
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "extraction.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (case_dir / "extraction.md").write_text(str(extraction.get("markdown") or ""), encoding="utf-8")

    errors = _assert_case(case, structured if isinstance(structured, dict) else {})
    return case, result, errors


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run GLM-OCR multi-pass extraction fixtures.")
    parser.add_argument("--input", default="./static_design/mathquestions", help="Fixture root directory")
    parser.add_argument("--out", default="./artifacts/extract_runs", help="Output artifacts root")
    args = parser.parse_args()

    root = Path(args.input).resolve()
    out_root = Path(args.out).resolve() / datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_root.mkdir(parents=True, exist_ok=True)

    cases = [c for c in _default_cases(root) if c.path.exists()]
    missing = [c for c in _default_cases(root) if not c.path.exists()]
    for m in missing:
        print(f"[WARN] missing fixture for role={m.role}: {m.path}")

    if not cases:
        print("[ERROR] no fixtures found")
        return 2

    results: List[Tuple[FixtureCase, Dict[str, Any], List[str]]] = []
    for case in cases:
        print(f"[RUN] {case.role}: {case.path.name}")
        results.append(await _run_case(case, out_root))

    summary_rows: List[Dict[str, Any]] = []
    total_errors = 0
    for case, result, errs in results:
        extraction = result.get("extraction") or {}
        row = {
            "role": case.role,
            "file": case.path.name,
            "source_type": case.source_type,
            "quality_score": extraction.get("quality_score"),
            "warnings": extraction.get("warnings"),
            "assertion_errors": errs,
        }
        summary_rows.append(row)
        if errs:
            total_errors += len(errs)
            print(f"[FAIL] {case.role}: {errs}")
        else:
            print(f"[PASS] {case.role}")

    (out_root / "summary.json").write_text(
        json.dumps(summary_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[DONE] artifacts={out_root}")
    return 1 if total_errors else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
