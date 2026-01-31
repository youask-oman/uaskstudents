import os
import base64
from typing import Optional

import requests


def send_whatsapp_message(to_jid: str, text: str) -> bool:
    """
    Send a WhatsApp message via the local Baileys bridge.
    Returns True on success, False on failure.
    """
    if not to_jid or not text:
        return False

    port = os.environ.get("WHATSAPP_INTERNAL_PORT", "8791")
    url = os.environ.get("WHATSAPP_INTERNAL_SEND_URL", f"http://orchestrator:{port}/send")
    key = os.environ.get("WHATSAPP_INTERNAL_KEY", "")

    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-UASK-INTERNAL-KEY"] = key

    try:
        resp = requests.post(url, json={"to": to_jid, "text": text}, headers=headers, timeout=5)
        return resp.status_code == 200
    except Exception as e:
        print(f"[WhatsApp] Failed to send message via bridge: {e}")
        return False


def send_whatsapp_image(to_jid: str, image_b64: str, content_type: str = "image/webp", caption: str = "") -> bool:
    if not to_jid or not image_b64:
        return False


def send_whatsapp_logo(to_jid: str) -> bool:
    path = os.environ.get("WHATSAPP_LOGO_PATH", "/app/app/assets/whatsapp_logo.png")
    if not to_jid:
        return False
    try:
        with open(path, "rb") as f:
            raw = f.read()
        if not raw:
            return False
        ext = os.path.splitext(path)[1].lower()
        content_type = "image/png" if ext == ".png" else "image/webp"
        return send_whatsapp_image(to_jid, base64.b64encode(raw).decode("utf-8"), content_type=content_type)
    except Exception as e:
        print(f"[WhatsApp] Failed to send logo: {e}")
        return False

    port = os.environ.get("WHATSAPP_INTERNAL_PORT", "8791")
    url = os.environ.get("WHATSAPP_INTERNAL_SEND_MEDIA_URL", f"http://orchestrator:{port}/send-media")
    key = os.environ.get("WHATSAPP_INTERNAL_KEY", "")

    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-UASK-INTERNAL-KEY"] = key

    try:
        payload = {
            "to": to_jid,
            "bytesBase64": image_b64,
            "contentType": content_type,
            "caption": caption or "",
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"[WhatsApp] Failed to send image via bridge: {e}")
        return False


def render_latex_via_bridge(latex: str, display_mode: bool = True) -> Optional[dict]:
    port = os.environ.get("WHATSAPP_INTERNAL_PORT", "8791")
    url = os.environ.get("WHATSAPP_INTERNAL_RENDER_URL", f"http://orchestrator:{port}/internal/latex/render")
    key = os.environ.get("WHATSAPP_INTERNAL_KEY", "")

    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-UASK-INTERNAL-KEY"] = key

    try:
        payload = {
            "latex": latex,
            "format": os.environ.get("WHATSAPP_LATEX_IMAGE_FORMAT", "webp"),
            "scale": 2,
            "displayMode": display_mode,
            "engine": os.environ.get("WHATSAPP_LATEX_RENDER_ENGINE", "katex"),
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception as e:
        print(f"[WhatsApp] Failed to render LaTeX via bridge: {e}")
        return None
