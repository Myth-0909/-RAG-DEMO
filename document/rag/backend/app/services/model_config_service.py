"""
Service to provide the current active LLM config from the database.
Falls back to settings (env vars) if no active config is found.
"""

import logging
from typing import Optional
from dataclasses import dataclass

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

_engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    model_name: str


def get_current_llm_config() -> LLMConfig:
    """
    Get the currently active LLM config.
    Returns the config marked as `is_current=True` from DB,
    or falls back to .env settings.
    """
    try:
        from app.models.model_config import ModelConfig

        db = _SessionLocal()
        try:
            config = (
                db.query(ModelConfig)
                .filter(
                    ModelConfig.config_type == "llm",
                    ModelConfig.is_current == True,
                )
                .first()
            )
            if config:
                logger.debug(f"Using DB LLM config: {config.name} ({config.model_name})")
                base_url = _normalize_base_url(config.base_url)
                return LLMConfig(
                    base_url=base_url,
                    api_key=config.api_key,
                    model_name=config.model_name,
                )
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"Could not load LLM config from DB: {e}")

    # Fallback to .env settings
    return LLMConfig(
        base_url=_normalize_base_url(settings.LLM_BASE_URL),
        api_key=settings.LLM_API_KEY,
        model_name=settings.LLM_MODEL,
    )


def _normalize_base_url(url: str) -> str:
    """
    Auto-fix common base_url mistakes:
    - Anthropic-compatible endpoints → OpenAI-compatible
    - Ensure URL ends with /v1 for OpenAI SDK compatibility
    """
    # Alibaba MaaS: /apps/anthropic → /compatible-mode/v1
    if "/apps/anthropic" in url:
        url = url.replace("/apps/anthropic", "/compatible-mode/v1")
        logger.info(f"Auto-fixed Anthropic endpoint → {url}")

    # Ensure trailing /v1
    url = url.rstrip("/")
    if not url.endswith("/v1"):
        url += "/v1"

    return url


def get_current_embedding_config() -> LLMConfig:
    """
    Get the currently active Embedding config.
    Returns the config marked as `is_current=True` from DB,
    or falls back to .env settings.
    """
    try:
        from app.models.model_config import ModelConfig

        db = _SessionLocal()
        try:
            config = (
                db.query(ModelConfig)
                .filter(
                    ModelConfig.config_type == "embedding",
                    ModelConfig.is_current == True,
                )
                .first()
            )
            if config:
                logger.debug(f"Using DB Embedding config: {config.name} ({config.model_name})")
                return LLMConfig(
                    base_url=config.base_url,
                    api_key=config.api_key,
                    model_name=config.model_name,
                )
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"Could not load Embedding config from DB: {e}")

    # Fallback to .env settings
    return LLMConfig(
        base_url=settings.EMBEDDING_BASE_URL,
        api_key=settings.EMBEDDING_API_KEY,
        model_name=settings.EMBEDDING_MODEL,
    )
