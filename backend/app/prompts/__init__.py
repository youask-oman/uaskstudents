"""Prompt management system for Math Solver."""

from .registry import (
    PromptRegistry,
    PromptTemplate,
    get_prompt_registry,
    get_prompt,
    get_schema
)

__all__ = [
    "PromptRegistry",
    "PromptTemplate",
    "get_prompt_registry",
    "get_prompt",
    "get_schema"
]
