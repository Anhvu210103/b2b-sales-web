"""Personalization package."""

from app.personalization.engine import PersonalizationEngine
from app.personalization.context_builder import ContextBuilder
from app.personalization.prompts import (
    EMAIL_PROMPTS,
    ZALO_PROMPTS,
    LINKEDIN_PROMPTS,
    FOLLOWUP_PROMPTS,
    get_prompt_for_channel,
)

__all__ = [
    "PersonalizationEngine",
    "ContextBuilder",
    "EMAIL_PROMPTS",
    "ZALO_PROMPTS",
    "LINKEDIN_PROMPTS",
    "FOLLOWUP_PROMPTS",
    "get_prompt_for_channel",
]