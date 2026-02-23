from __future__ import annotations

from typing import Any, Dict, List


def build_plot_telemetry(
    *,
    classification: str,
    normalized_recipe: Dict[str, Any],
    sampling: Dict[str, Any],
    warnings: List[str],
    errors: List[str],
    fallback_used: bool,
) -> Dict[str, Any]:
    return {
        "classification": classification,
        "normalized_recipe": normalized_recipe,
        "sampling": sampling,
        "warnings": list(warnings or []),
        "errors": list(errors or []),
        "fallback_used": bool(fallback_used),
    }

