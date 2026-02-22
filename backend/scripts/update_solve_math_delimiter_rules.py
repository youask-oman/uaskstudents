from __future__ import annotations

from sqlmodel import Session, select

from app.database import engine
from app.models import PromptModeEnum, PromptTemplateEntry

RULE_BLOCK = """

Output Math Delimiter Rules (MANDATORY):
- Use \\( ... \\) for inline math.
- Use \\[ ... \\] for display math (multi-line, aligned, or important equations).
- Do NOT wrap equations in plain square brackets like [ ... ].
"""


def main() -> None:
    updated = 0
    with Session(engine) as session:
        rows = session.exec(
            select(PromptTemplateEntry)
            .where(PromptTemplateEntry.mode == PromptModeEnum.SOLVE)
            .where(PromptTemplateEntry.is_active == True)
        ).all()

        for row in rows:
            content = str(row.content or "")
            if "Output Math Delimiter Rules (MANDATORY)" in content:
                continue
            row.content = f"{content.rstrip()}\n{RULE_BLOCK}".strip()
            row.updated_by = "script:update_solve_math_delimiter_rules"
            session.add(row)
            updated += 1

        session.commit()

    print(f"updated_active_solve_prompts={updated}")


if __name__ == "__main__":
    main()

