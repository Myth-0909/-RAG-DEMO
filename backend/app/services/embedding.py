from openai import OpenAI
from typing import List
from app.config import settings
from app.services.model_config_service import get_current_embedding_config
import httpx
import logging

logger = logging.getLogger(__name__)


def get_embedding_client() -> OpenAI:
    """动态获取 Embedding 客户端，支持从数据库读取配置

    Uses trust_env=False to bypass system HTTP_PROXY settings, which would
    otherwise route internal-network requests through an external proxy and
    cause 502 errors.
    """
    cfg = get_current_embedding_config()
    http_client = httpx.Client(transport=httpx.HTTPTransport(trust_env=False))
    return OpenAI(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        http_client=http_client,
    )


def get_current_model_name() -> str:
    """获取当前 Embedding 模型名称"""
    cfg = get_current_embedding_config()
    return cfg.model_name


def embed_texts(texts: List[str]) -> List[List[float]]:
    client = get_embedding_client()
    response = client.embeddings.create(
        model=get_current_model_name(),
        input=texts,
    )
    return [item.embedding for item in response.data]


def embed_query(text: str) -> List[float]:
    return embed_texts([text])[0]
