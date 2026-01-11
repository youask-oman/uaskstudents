from sqlmodel import select
from app.models import PromptTemplate, PromptVersion

def get_active_prompt(slug: str, session) -> str:
    """
    Retrieves the content of the currently active 'production' prompt version
    for the given template slug. Returns None if not found.
    """
    # 1. Find the template
    template = session.exec(select(PromptTemplate).where(PromptTemplate.slug == slug)).first()
    if not template:
        return None
    
    # 2. Find the active production version
    stmt = select(PromptVersion).where(
        PromptVersion.template_id == template.id,
        PromptVersion.is_production == True
    ).order_by(PromptVersion.created_at.desc())
    
    version = session.exec(stmt).first()
    
    if version:
        return version.content
    return None
