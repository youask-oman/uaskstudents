#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from threading import Semaphore
from typing import Any, Dict, List

import requests


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
PDF_EXTS = {".pdf"}


def _iter_dataset_files(root: Path) -> List[Path]:
    out: List[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS.union(PDF_EXTS):
            out.append(p)
    return sorted(out)


def _safe_name(path: Path) -> str:
    base = path.stem.replace(" ", "_")
    return "".join(ch if (ch.isalnum() or ch in {"_", "-", "."}) else "_" for ch in base)


def _extract_one(*, api_url: str, path: Path, max_pages: int, enable_layout: bool, semaphore: Semaphore, out_dir: Path, timeout_seconds: int) -> Dict[str, Any]:
    ext = path.suffix.lower()
    source_type = "pdf" if ext in PDF_EXTS else "image"
    item_dir = out_dir / f"{_safe_name(path)}_{abs(hash(str(path))) % 100000}"
    item_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    response_payload: Dict[str, Any] = {}
    status = "ok"
    error = ""

    with semaphore:
        with path.open("rb") as f:
            files = {"file": (path.name, f, "application/pdf" if source_type == "pdf" else "application/octet-stream")}
            data = {
                "source_type": source_type,
                "max_pages": str(max_pages),
                "enable_layout": "true" if enable_layout else "false",
                "keep_rendered_pages": "true",
            }
            try:
                resp = requests.post(api_url, files=files, data=data, timeout=timeout_seconds)
                if resp.status_code >= 400:
                    status = "error"
                    error = f"HTTP {resp.status_code}: {resp.text[:1200]}"
                else:
                    response_payload = resp.json()
            except Exception as exc:
                status = "error"
                error = f"{type(exc).__name__}: {exc}"

    runtime_ms = int((time.perf_counter() - started) * 1000)

    extraction = (response_payload or {}).get("extraction") or {}
    source = (response_payload or {}).get("source") or {}
    markdown = str(extraction.get("markdown") or "")
    json_out = extraction.get("json") if isinstance(extraction.get("json"), dict) else {"raw": extraction.get("json")}
    quality_score = float(extraction.get("quality_score") or 0.0)
    warnings = extraction.get("warnings") or []
    backend_used = str(extraction.get("backend_used") or "unknown")
    page_count = source.get("page_count")
    rendered_debug_dir = source.get("rendered_debug_dir")
    extracted_char_count = len(str(extraction.get("question_text") or "").strip())

    if status != "ok":
        markdown = ""
        json_out = {"error": error}
        warnings = [error]
        backend_used = "failed"
        quality_score = 0.0
        extracted_char_count = 0

    (item_dir / "extraction.md").write_text(markdown, encoding="utf-8")
    extraction_json_payload = response_payload if status == "ok" else {
        "source": {"filename": path.name, "type": source_type, "pages": []},
        "extraction": {
            "question_text": "",
            "question_latex": "",
            "markdown": markdown,
            "json": json_out,
            "warnings": warnings,
            "quality_score": quality_score,
            "backend_used": backend_used,
        },
    }
    (item_dir / "extraction.json").write_text(json.dumps(extraction_json_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    if source_type == "pdf" and rendered_debug_dir:
        try:
            src_dir = Path(str(rendered_debug_dir))
            if src_dir.exists() and src_dir.is_dir():
                dst_dir = item_dir / "rendered_pages"
                if dst_dir.exists():
                    shutil.rmtree(dst_dir)
                shutil.copytree(src_dir, dst_dir)
        except Exception:
            pass

    return {
        "filename": str(path),
        "type": source_type,
        "page_count": page_count if page_count is not None else (1 if source_type == "image" else None),
        "runtime_ms": runtime_ms,
        "quality_score": quality_score,
        "warnings_count": len(warnings),
        "extracted_char_count": extracted_char_count,
        "backend_used": backend_used,
        "status": status,
        "error": error,
        "artifact_dir": str(item_dir),
        "rendered_debug_dir": str(rendered_debug_dir or ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run GLM-OCR dataset extraction regression on ./mathquestions")
    parser.add_argument("--input", default="./mathquestions", help="Input dataset directory")
    parser.add_argument("--out", default="./artifacts/glmocr_runs", help="Output root directory")
    parser.add_argument("--api-url", default="http://localhost:9000/api/extract/math-question", help="Extraction API URL")
    parser.add_argument("--max-pages", type=int, default=5, help="Max PDF pages")
    parser.add_argument("--max-workers", type=int, default=4, help="Parallel workers")
    parser.add_argument("--timeout", type=int, default=300, help="Request timeout seconds")
    parser.add_argument("--enable-layout", action="store_true", help="Enable GLM-OCR layout parsing")
    args = parser.parse_args()

    input_dir = Path(args.input).resolve()
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    files = _iter_dataset_files(input_dir)
    if not files:
        print(f"No supported files found in {input_dir}")
        return 1

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(args.out).resolve() / ts
    run_dir.mkdir(parents=True, exist_ok=True)

    semaphore = Semaphore(max(1, args.max_workers))
    rows: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.max_workers)) as pool:
        futures = [
            pool.submit(
                _extract_one,
                api_url=args.api_url,
                path=f,
                max_pages=max(1, args.max_pages),
                enable_layout=bool(args.enable_layout),
                semaphore=semaphore,
                out_dir=run_dir,
                timeout_seconds=max(30, args.timeout),
            )
            for f in files
        ]
        for fut in as_completed(futures):
            row = fut.result()
            rows.append(row)
            print(
                f"{row['status']:>5} | {row['runtime_ms']:>6}ms | q={row['quality_score']:.3f} "
                f"| backend={row['backend_used']:<15} | {row['filename']}"
            )

    rows = sorted(rows, key=lambda x: x["filename"])
    summary_json_path = run_dir / "summary.json"
    summary_csv_path = run_dir / "summary.csv"
    summary_json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    with summary_csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "filename",
                "type",
                "page_count",
                "runtime_ms",
                "quality_score",
                "warnings_count",
                "extracted_char_count",
                "backend_used",
                "status",
                "error",
                "artifact_dir",
                "rendered_debug_dir",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    failures = [r for r in rows if r["status"] != "ok"]
    lowest_quality = sorted(rows, key=lambda r: r["quality_score"])[:10]
    highest_latency = sorted(rows, key=lambda r: r["runtime_ms"], reverse=True)[:10]
    empty_outputs = [r for r in rows if r["extracted_char_count"] == 0]

    print("\nTop lowest quality:")
    for row in lowest_quality:
        print(f"- q={row['quality_score']:.3f} | {row['filename']}")

    print("\nTop highest latency:")
    for row in highest_latency:
        print(f"- {row['runtime_ms']}ms | {row['filename']}")

    print("\nEmpty outputs:")
    for row in empty_outputs[:20]:
        print(f"- {row['filename']} (status={row['status']}, backend={row['backend_used']})")

    print(f"\nSummary JSON: {summary_json_path}")
    print(f"Summary CSV : {summary_csv_path}")
    print(f"Failures    : {len(failures)} / {len(rows)}")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
