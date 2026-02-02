from sqlmodel import select
from app.models import PromptTemplateEntry

def get_active_prompt(slug: str, session) -> str:
    """
    Retrieves active prompt content by prompt_id from prompt_templates registry table.
    Returns None if not found.
    """
    entry = session.exec(
        select(PromptTemplateEntry)
        .where(PromptTemplateEntry.prompt_id == slug)
        .where(PromptTemplateEntry.is_active == True)
        .order_by(PromptTemplateEntry.version.desc())
    ).first()
    return entry.content if entry else None
