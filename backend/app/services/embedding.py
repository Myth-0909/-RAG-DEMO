from openai import OpenAI
from typing import List
from app.config import settings

_client = None


def get_embedding_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=settings.EMBEDDING_BASE_URL,
            api_key=settings.EMBEDDING_API_KEY,
        )
    return _client


def embed_texts(texts: List[str]) -> List[List[float]]:
    client = get_embedding_client()
    response = client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


def embed_query(text: str) -> List[float]:
    return embed_texts([text])[0]
