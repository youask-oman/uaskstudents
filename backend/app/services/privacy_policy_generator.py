from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def _inventory_candidates() -> List[Path]:
    here = Path(__file__).resolve()
    return [
        here.parents[3] / "privacy_data_inventory.json",  # local repo layout
        here.parents[2] / "privacy_data_inventory.json",  # docker /app/app layout
        Path.cwd() / "privacy_data_inventory.json",
        Path.cwd().parent / "privacy_data_inventory.json",
        Path("/src/privacy_data_inventory.json"),  # docker compose repo mount
    ]


def load_privacy_inventory() -> Dict[str, Any]:
    for inventory_path in _inventory_candidates():
        if inventory_path.exists():
            with inventory_path.open("r", encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError("privacy_data_inventory.json not found in expected locations")


def _bullets(items: List[str]) -> str:
    return "\n".join([f"- {item}" for item in items])


def build_privacy_policy_markdown() -> str:
    inv = load_privacy_inventory()
    meta = inv.get("meta", {})
    sections = inv.get("sections", {})
    categories = inv.get("data_categories", [])

    collect_lines: List[str] = []
    retention_lines: List[str] = []
    processors = set()
    for category in categories:
        name = category.get("data_category", "Data")
        fields = category.get("fields_examples", [])
        purpose = category.get("purpose", "")
        retention = category.get("retention", "")
        procs = category.get("processors", [])
        processors.update([p for p in procs if isinstance(p, str) and p.strip()])
        field_str = ", ".join(fields) if fields else "N/A"
        collect_lines.append(f"**{name}:** {field_str}. Purpose: {purpose}.")
        retention_lines.append(f"- {name}: {retention}")

    processors_list = ", ".join(sorted(processors)) if processors else "service providers/processors"

    return f"""# Privacy Policy (uask.ai)

**Effective date:** {meta.get("effective_date", "[EFFECTIVE_DATE]")}  
**Last updated:** {meta.get("last_updated_date", "[LAST_UPDATED_DATE]")}

This Privacy Policy explains how **uask.ai** ("uask.ai", "we", "us") collects, uses, shares, and protects information when you use our website, apps, and services (the "Service").

If you do not agree with this policy, do not use the Service.

## 1) Who we are
- **Service name:** uask.ai  
- **Operator:** {meta.get("legal_entity_name", "[LEGAL_ENTITY_NAME]")}  
- **Contact email:** {meta.get("privacy_contact_email", "[PRIVACY_CONTACT_EMAIL]")}  
- **Business address (if applicable):** {meta.get("business_address", "[BUSINESS_ADDRESS]")}

## 2) Information we collect
We collect information in three main ways: (a) information you provide, (b) information generated through your use of the Service, and (c) information from service providers (e.g., payment processors).

{_bullets(collect_lines)}

**Important:** Uploaded files may contain personal information if you include it. Please avoid uploading sensitive personal information unless necessary.

## 3) How we use information
We use information to:
{_bullets(sections.get("how_we_use", []))}

## 4) Legal bases (where required)
Where required by law (e.g., GDPR/UK GDPR), we rely on:
- Performance of a contract (providing the Service)
- Legitimate interests (security, fraud prevention, service improvement)
- Consent (certain cookies/marketing, where applicable)
- Legal obligations (tax, accounting, lawful requests)

## 5) How AI processing works
To generate solutions and explanations, we may process your prompts and uploaded content using:
- Our own systems and models, and/or
- Third-party AI service providers acting as processors.

We send only the information needed to provide the requested feature (e.g., OCR extraction or solution generation). We do not intentionally request sensitive personal information.

## 6) How we share information
We may share information with:
- **Service providers/processors** that help operate the Service, including: {processors_list}.
- **Legal and safety**: to comply with law, respond to lawful requests, or protect the rights, safety, and security of users and the Service.
- **Business changes**: if we are involved in a merger, acquisition, financing, or sale of assets, information may be transferred as part of that transaction.

We do **not** sell personal information in the traditional sense. If applicable privacy laws define "sale" or "share" broadly (e.g., for targeted advertising), we will provide a way to opt out.

## 7) Data retention
We retain information only as long as necessary for the purposes described:
{chr(10).join(retention_lines)}
- Payment and invoice records: as required by tax/accounting laws

You may request deletion as described below, but we may retain certain information for legal, security, or fraud-prevention reasons.

## 8) Security
We use reasonable administrative, technical, and organizational safeguards designed to protect information, such as:
{_bullets(sections.get("security_controls", []))}

No system is 100% secure. Please use a strong password and do not share credentials.

## 9) Children's privacy
The Service is not directed to children under {meta.get("child_age_threshold", "[CHILD_AGE_THRESHOLD]")}. If you believe a child provided personal information, contact us and we will take appropriate steps to delete it.

## 10) International data transfers
We may process and store information in countries where we or our providers operate. Those countries may have different data protection laws than your jurisdiction. We take steps to protect information in accordance with this policy.

## 11) Your rights and choices
Depending on your location, you may have rights to:
{_bullets(sections.get("rights", []))}

To make a request, contact: **{meta.get("privacy_contact_email", "[PRIVACY_CONTACT_EMAIL]")}**  
We may need to verify your identity before fulfilling requests.

## 12) Third-party links
The Service may contain links to third-party websites. We are not responsible for their privacy practices.

## 13) Changes to this policy
We may update this Privacy Policy from time to time. We will post the updated version with a new "Effective date." If changes are material, we will provide additional notice (e.g., in-app notice or email).

## 14) Contact us
Questions or concerns:
- Email: **{meta.get("privacy_contact_email", "[PRIVACY_CONTACT_EMAIL]")}**
- Address: {meta.get("business_address", "[BUSINESS_ADDRESS]")}
"""
