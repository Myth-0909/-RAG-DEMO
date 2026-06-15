from openai import OpenAI
from typing import List
from app.config import settings
from app.services.model_config_service import get_current_embedding_config
import logging

logger = logging.getLogger(__name__)


def get_embedding_client() -> OpenAI:
    """动态获取 Embedding 客户端，支持从数据库读取配置"""
    cfg = get_current_embedding_config()
    return OpenAI(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
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
