import os
import uuid
from typing import Dict, Any, List, Optional

from app.services.whatsapp.latex_parser import extract_latex, normalize_latex
from app.services.whatsapp.whatsapp_send import send_whatsapp_message, send_whatsapp_image, render_latex_via_bridge
from app.services.whatsapp.whatsapp_state import set_step_pack, get_step_pack


def _cap_blocks(blocks: List[Dict[str, str]]) -> List[Dict[str, str]]:
    cap = int(os.environ.get("WHATSAPP_LATEX_MAX_BLOCKS_PER_REPLY", "10"))
    return blocks[:cap]


def _looks_like_latex(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if "\\" in text:
        return True
    if "^" in text or "_" in text:
        return True
    return any(tok in lowered for tok in ("sqrt", "frac", "sum", "int", "lim"))


def build_step_pack(from_jid: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    pack_steps = []
    for i, step in enumerate(steps, 1):
        title = step.get("title") or f"Step {i}"
        explanation = step.get("explanation") or ""

        latex_blocks = []
        math = step.get("math") or {}
        latex_lines = math.get("latex_lines") or []
        for line in latex_lines:
            if line:
                latex_blocks.append({"type": "block", "latex": line})

        extra_blocks, plain = extract_latex(explanation)
        latex_blocks.extend(extra_blocks)

        text_out = plain or explanation
        if not latex_blocks and _looks_like_latex(explanation):
            latex_blocks.append({"type": "inline", "latex": normalize_latex(explanation)})
            text_out = ""

        pack_steps.append({
            "index": i,
            "title": title,
            "text": text_out,
            "equations": _cap_blocks(latex_blocks),
        })

    return {
        "id": uuid.uuid4().hex,
        "from": from_jid,
        "steps": pack_steps,
        "current_index": 1,
    }


def send_step(from_jid: str, step: Dict[str, Any], total_steps: int) -> None:
    header = f"Step {step['index']}/{total_steps}: {step['title']}"
    body = step.get("text", "")
    send_whatsapp_message(from_jid, f"{header}\n{body}".strip())

    for eq in step.get("equations", []):
        latex = eq.get("latex", "")
        if not latex:
            continue
        rendered = render_latex_via_bridge(latex, display_mode=(eq.get("type") == "block"))
        if rendered and rendered.get("bytesBase64"):
            send_whatsapp_image(from_jid, rendered["bytesBase64"], rendered.get("contentType", "image/webp"))
        else:
            send_whatsapp_message(from_jid, f"Could not render equation:\n`{latex}`")


def send_step_pack(from_jid: str, pack: Dict[str, Any], index: int) -> None:
    steps = pack.get("steps", [])
    if not steps:
        return
    index = max(1, min(index, len(steps)))
    step = steps[index - 1]
    send_step(from_jid, step, len(steps))


def handle_navigation(from_jid: str, text: str) -> bool:
    pack = get_step_pack(from_jid)
    if not pack:
        return False

    upper = text.strip().upper()
    if upper in ("NEXT", "N", "2"):
        pack["current_index"] = min(pack.get("current_index", 1) + 1, len(pack.get("steps", [])))
    elif upper in ("PREV", "P", "3"):
        pack["current_index"] = max(pack.get("current_index", 1) - 1, 1)
    elif upper in ("ALL", "A"):
        for step in pack.get("steps", []):
            send_step(from_jid, step, len(pack.get("steps", [])))
        return True
    elif upper.isdigit():
        pack["current_index"] = max(1, min(int(upper), len(pack.get("steps", []))))
    else:
        return False

    set_step_pack(from_jid, pack)
    send_step_pack(from_jid, pack, pack.get("current_index", 1))
    return True
