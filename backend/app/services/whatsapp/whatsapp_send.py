import os
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
