"""Utility modules for the uask backend."""

# Import from schema_deref submodule
from .schema_deref import (
    deref_json_schema,
    validate_no_refs,
    get_deref_schema_for_openai,
    CyclicReferenceError
)

# Legacy import - preserve backward compatibility with old utils.py
# This was previously in app/utils.py
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


__all__ = [
    # Schema deref
    "deref_json_schema",
    "validate_no_refs", 
    "get_deref_schema_for_openai",
    "CyclicReferenceError",
    # Legacy
    "get_active_prompt"
]
