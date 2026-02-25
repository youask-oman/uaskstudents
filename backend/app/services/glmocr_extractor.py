from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.services.glmocr_direct import run_glmocr_prompt
from app.services.glmocr_extract_router import detect_content_types
from app.services.glmocr_prompts import (
    GLMOCR_GEOMETRY_DIAGRAM_PROMPT,
    GLMOCR_GRAPH_EXTRACTION_PROMPT,
    GLMOCR_MCQ_STRUCT_PROMPT,
    GLMOCR_MEASUREMENT_RECOVERY_PROMPT,
    GLMOCR_TABLE_EXTRACTION_PROMPT,
    GLMOCR_TRANSCRIBE_PROMPT,
)
from app.services.quality_score import compute_quality_score


_MCQ_VALID_LABELS = set("ABCDEFGHJKLMNPQRSTUVWXYZ")


def _extract_choices(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    current_key: Optional[str] = None
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = re.match(r"(?i)^\s*[\(\[]?([A-Z])[\)\].:]\s*(.+)$", line)
        if m:
            label = m.group(1).upper()
            if label not in _MCQ_VALID_LABELS:
                continue
            current_key = label
            out[current_key] = m.group(2).strip()
            continue
        if current_key and current_key in out:
            out[current_key] = f"{out[current_key]} {line}".strip()
    return out


def _extract_stem(text: str) -> str:
    src = text or ""
    m = re.search(r"(?is)STEM:\s*(.+?)(?:\n\s*CHOICES:|\Z)", src)
    if m:
        return m.group(1).strip()
    lines: List[str] = []
    for line in src.splitlines():
        if re.match(r"(?i)^\s*[\(\[]?[A-Z][\)\].:]\s+", line.strip()):
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _extract_axis_label(text: str, axis: str) -> Optional[str]:
    patts = [
        rf"(?im)^\s*(?:[-*]\s*)?{axis}\s*[-_ ]?label\s*[:\-]\s*(.+)$",
        rf"(?im)^\s*(?:[-*]\s*)?{axis}\s*[-_ ]?axis\s*[:\-]\s*(.+)$",
        rf"(?im)^\s*(?:[-*]\s*)?{axis}\s*[-_ ]?axis\s*label\s*[:\-]\s*(.+)$",
    ]
    for patt in patts:
        m = re.search(patt, text or "")
        if m:
            return m.group(1).strip()
    return None


def _extract_ticks(text: str, axis: str) -> Optional[List[str]]:
    patt = rf"(?im)^\s*(?:[-*]\s*)?{axis}\s*(?:[-_ ]?axis)?\s*[-_ ]?ticks?\s*[:\-]\s*(.+)$"
    m = re.search(patt, text or "")
    if not m:
        return None
    raw = m.group(1).strip()
    tokens = [t.strip() for t in re.split(r"[,;]\s*|\s{2,}", raw) if t.strip()]
    return tokens or None


def _extract_list_by_prefix(text: str, prefixes: List[str]) -> Optional[List[str]]:
    out: List[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        clean = stripped.lstrip("-* ").strip()
        low = clean.lower()
        if any(low.startswith(prefix) for prefix in prefixes):
            val = clean.split(":", 1)[1].strip() if ":" in clean else clean
            if val:
                out.append(val)
    return out or None


def _extract_equations(text: str) -> List[str]:
    found = re.findall(r"(?:(?:^|\s)([xy]\s*=\s*[^,\n;]+))", text or "", flags=re.IGNORECASE)
    uniq: List[str] = []
    seen = set()
    for item in found:
        val = item.strip()
        key = val.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(val)
    return uniq


def _build_graph_block(text: str) -> Dict[str, Any]:
    legend = _extract_list_by_prefix(text, ["legend", "legend entry", "legend entries"])
    if not legend:
        inferred_legend: List[str] = []
        for line in (text or "").splitlines():
            stripped = line.strip(" -*\t")
            if not stripped:
                continue
            low = stripped.lower()
            if "curve" in low or "line" in low or "function" in low:
                inferred_legend.append(stripped)
        legend = inferred_legend or None
    explicit_eq = _extract_equations(text)
    if not legend and explicit_eq:
        legend = explicit_eq.copy()
    curves: List[Dict[str, Any]] = []
    for idx, line in enumerate(legend or []):
        eq_for_curve = next((eq for eq in explicit_eq if eq.lower() in line.lower()), None)
        curves.append(
            {
                "name": line,
                "style": None,
                "explicit_equation": eq_for_curve or (explicit_eq[idx] if idx < len(explicit_eq) else None),
            }
        )
    if not curves and explicit_eq:
        for eq in explicit_eq:
            curves.append({"name": eq, "style": None, "explicit_equation": eq})
    ann = _extract_list_by_prefix(
        text,
        ["point", "intercept", "asymptote", "annotation", "- point", "- intercept", "- asymptote"],
    ) or []
    return {
        "x_label": _extract_axis_label(text, "x"),
        "y_label": _extract_axis_label(text, "y"),
        "x_ticks": _extract_ticks(text, "x"),
        "y_ticks": _extract_ticks(text, "y"),
        "legend": legend,
        "curves": curves,
        "explicit_annotations": ann,
    }


def _parse_table_markdown_and_csv(text: str) -> Dict[str, str]:
    src = text or ""
    md_match = re.search(r"(?is)(\|.+\|(?:\n\|.*\|)+)", src)
    csv_match = re.search(r"(?is)CSV(?:\s+version)?\s*:?\s*\n(.+)", src)
    markdown = md_match.group(1).strip() if md_match else src.strip()
    csv = ""
    if csv_match:
        csv = csv_match.group(1).strip()
    elif md_match:
        lines = [l.strip() for l in markdown.splitlines() if l.strip()]
        rows: List[str] = []
        for line in lines:
            if set(line.replace("|", "").replace("-", "").strip()) == set():
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            rows.append(",".join(cells))
        csv = "\n".join(rows)
    return {"markdown": markdown, "csv": csv}


def _build_geometry_block(text: str) -> Dict[str, Any]:
    src = text or ""
    obj_words = ["cone", "cylinder", "circle", "triangle", "rectangle", "sphere", "prism"]
    objects = [w for w in obj_words if re.search(rf"(?i)\b{w}\b", src)]
    dim_lines: List[str] = []
    for line in src.splitlines():
        stripped = line.strip(" -*\t")
        if re.search(r"(?i)\b\d+(?:\.\d+)?\s*(ft|cm|mm|m|in|inch|inches)\b", stripped):
            dim_lines.append(stripped)
    if not dim_lines:
        dims = re.findall(r"(?i)\b(\d+(?:\.\d+)?)\s*(ft|cm|mm|m|in|inch|inches)\b", src)
        for val, unit in dims:
            dim_lines.append(f"{val} {unit}")
    relationships = []
    for word in ["parallel", "perpendicular", "congruent", "equal", "right angle"]:
        if re.search(rf"(?i)\b{re.escape(word)}\b", src):
            relationships.append(word)
    return {
        "objects": sorted(set(objects)),
        "dimensions": sorted(set(dim_lines)),
        "relationships": sorted(set(relationships)),
    }


def _parse_measurement_lines(text: str) -> List[str]:
    out: List[str] = []
    for line in (text or "").splitlines():
        if re.search(r"(?i)\b\d+(?:\.\d+)?\s*(ft|cm|mm|m|in|inch|inches)\b", line):
            out.append(line.strip())
    return out


async def extract_structured_from_image(
    *,
    image_bytes: bytes,
    request_id: str,
    filename: str,
    page: Optional[int] = None,
) -> Dict[str, Any]:
    first = await run_glmocr_prompt(
        image_bytes=image_bytes,
        request_id=f"{request_id}-raw",
        prompt=GLMOCR_TRANSCRIBE_PROMPT,
        filename=filename,
    )
    raw_text = str(first.get("response_text") or "").strip()
    detected = detect_content_types(raw_text)

    pass_outputs: Dict[str, str] = {}
    if detected.get("has_mcq"):
        out = await run_glmocr_prompt(
            image_bytes=image_bytes,
            request_id=f"{request_id}-mcq",
            prompt=GLMOCR_MCQ_STRUCT_PROMPT,
            filename=filename,
        )
        pass_outputs["mcq"] = str(out.get("response_text") or "")
    if detected.get("has_graph"):
        out = await run_glmocr_prompt(
            image_bytes=image_bytes,
            request_id=f"{request_id}-graph",
            prompt=GLMOCR_GRAPH_EXTRACTION_PROMPT,
            filename=filename,
        )
        pass_outputs["graph"] = str(out.get("response_text") or "")
    if detected.get("has_table"):
        out = await run_glmocr_prompt(
            image_bytes=image_bytes,
            request_id=f"{request_id}-table",
            prompt=GLMOCR_TABLE_EXTRACTION_PROMPT,
            filename=filename,
        )
        pass_outputs["table"] = str(out.get("response_text") or "")
    if detected.get("has_geometry") or detected.get("units_detected"):
        out = await run_glmocr_prompt(
            image_bytes=image_bytes,
            request_id=f"{request_id}-geometry",
            prompt=GLMOCR_GEOMETRY_DIAGRAM_PROMPT,
            filename=filename,
        )
        pass_outputs["geometry"] = str(out.get("response_text") or "")
        out_m = await run_glmocr_prompt(
            image_bytes=image_bytes,
            request_id=f"{request_id}-measurements",
            prompt=GLMOCR_MEASUREMENT_RECOVERY_PROMPT,
            filename=filename,
        )
        pass_outputs["measurements_only"] = str(out_m.get("response_text") or "")

    mcq = None
    if "mcq" in pass_outputs:
        choices = _extract_choices(pass_outputs["mcq"])
        if len(choices) < 3:
            # Fallback to raw transcription when the structured MCQ pass is sparse.
            choices = _extract_choices(raw_text)
        notes = []
        if len(choices) < 3:
            notes.append("INCOMPLETE_CHOICES")
        mcq = {
            "stem": _extract_stem(pass_outputs["mcq"]) or raw_text,
            "choices": choices,
            "notes": notes,
        }

    graph = _build_graph_block(pass_outputs.get("graph", "")) if "graph" in pass_outputs else None
    if graph and not any([graph.get("x_label"), graph.get("y_label"), graph.get("x_ticks"), graph.get("y_ticks"), graph.get("legend")]):
        fallback_graph = _build_graph_block(raw_text)
        if any(
            [
                fallback_graph.get("x_label"),
                fallback_graph.get("y_label"),
                fallback_graph.get("x_ticks"),
                fallback_graph.get("y_ticks"),
                fallback_graph.get("legend"),
            ]
        ):
            graph = fallback_graph
    table = _parse_table_markdown_and_csv(pass_outputs["table"]) if "table" in pass_outputs else None
    geometry = _build_geometry_block(pass_outputs.get("geometry", "")) if "geometry" in pass_outputs else None
    measurements_only = (
        _parse_measurement_lines(pass_outputs.get("measurements_only", "")) if "measurements_only" in pass_outputs else None
    )

    quality_score, quality_warnings = compute_quality_score(raw_text, raw_text)
    if detected.get("has_mcq") and mcq and len(mcq["choices"]) < 3:
        quality_warnings.append("MCQ_CHOICES_MISSING")
    if detected.get("units_detected") and not measurements_only:
        quality_warnings.append("UNITS_DETECTED_BUT_MEASUREMENTS_EMPTY")

    return {
        "raw": {
            "transcription": raw_text,
            "source_image": {"file": filename, "page": page},
        },
        "detected": {
            "has_mcq": bool(detected.get("has_mcq")),
            "has_graph": bool(detected.get("has_graph")),
            "has_table": bool(detected.get("has_table")),
            "has_geometry": bool(detected.get("has_geometry")),
        },
        "mcq": mcq,
        "graph": graph,
        "table": table,
        "geometry": geometry,
        "measurements_only": measurements_only,
        "quality": {
            "score": max(0.0, min(1.0, float(quality_score))),
            "warnings": sorted({str(w) for w in quality_warnings if w}),
        },
    }


def merge_structured_pages(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged_transcription = "\n\n".join(
        str((p.get("raw") or {}).get("transcription") or "").strip() for p in pages if p
    ).strip()
    has_mcq = any(bool((p.get("detected") or {}).get("has_mcq")) for p in pages)
    has_graph = any(bool((p.get("detected") or {}).get("has_graph")) for p in pages)
    has_table = any(bool((p.get("detected") or {}).get("has_table")) for p in pages)
    has_geometry = any(bool((p.get("detected") or {}).get("has_geometry")) for p in pages)

    first_non_null = lambda key: next((p.get(key) for p in pages if p.get(key) is not None), None)
    quality_scores = [float((p.get("quality") or {}).get("score") or 0.0) for p in pages]
    all_warnings: List[str] = []
    for p in pages:
        all_warnings.extend((p.get("quality") or {}).get("warnings") or [])

    return {
        "raw": {
            "transcription": merged_transcription,
            "source_image": (
                (pages[0].get("raw") or {}).get("source_image")
                if len(pages) == 1 and isinstance(pages[0], dict)
                else {"file": None, "page": None}
            ),
        },
        "detected": {
            "has_mcq": has_mcq,
            "has_graph": has_graph,
            "has_table": has_table,
            "has_geometry": has_geometry,
        },
        "mcq": first_non_null("mcq"),
        "graph": first_non_null("graph"),
        "table": first_non_null("table"),
        "geometry": first_non_null("geometry"),
        "measurements_only": first_non_null("measurements_only"),
        "quality": {
            "score": (sum(quality_scores) / len(quality_scores)) if quality_scores else 0.0,
            "warnings": sorted({str(w) for w in all_warnings if w}),
        },
    }
