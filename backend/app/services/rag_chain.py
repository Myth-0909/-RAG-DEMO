from typing import List, Dict, Any, AsyncGenerator
from sqlalchemy.orm import Session
from app.services.milvus_service import MilvusService
from app.services.embedding import embed_query
from app.models.knowledge import KnowledgeBase, Document, Domain
from app.config import settings
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

_llm_client = None


def get_llm_client() -> OpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = OpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
        )
    return _llm_client


def retrieve_context(
    question: str,
    knowledge_base_ids: List[int],
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    query_embedding = embed_query(question)
    milvus = MilvusService()
    all_hits = []

    for kb_id in knowledge_base_ids:
        collection_name = f"kb_{kb_id}"
        try:
            hits = milvus.search(
                collection_name=collection_name,
                query_embedding=query_embedding,
                top_k=top_k,
            )
            for hit in hits:
                hit["knowledge_base_id"] = kb_id
            all_hits.extend(hits)
        except Exception as e:
            logger.warning(f"Search failed for collection {collection_name}: {e}")

    all_hits.sort(key=lambda x: x["score"], reverse=True)
    return all_hits[:top_k]


def build_context_text(hits: List[Dict[str, Any]]) -> str:
    parts = []
    for i, hit in enumerate(hits, 1):
        text = hit.get("parent_text") or hit.get("chunk_text", "")
        parts.append(f"[{i}] {text}")
    return "\n\n".join(parts)


def get_system_prompt(domain_id: int = None, db: Session = None) -> str:
    base_prompt = """你是一个专业的知识库问答助手。请根据提供的上下文信息回答用户的问题。

规则：
1. 仅基于提供的上下文信息回答，不要编造信息
2. 如果上下文中没有相关信息，请明确告知用户
3. 回答时引用来源编号，如 [1]、[2]
4. 保持回答简洁、准确、专业"""

    if domain_id and db:
        domain = db.query(Domain).filter(Domain.id == domain_id).first()
        if domain and domain.system_prompt:
            return f"{base_prompt}\n\n专业领域指导：{domain.system_prompt}"

    return base_prompt


async def rag_query(
    question: str,
    knowledge_base_ids: List[int],
    domain_id: int = None,
    top_k: int = 5,
    db: Session = None,
) -> Dict[str, Any]:
    hits = retrieve_context(question, knowledge_base_ids, top_k)
    context = build_context_text(hits)
    system_prompt = get_system_prompt(domain_id, db)

    client = get_llm_client()
    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"上下文信息：\n{context}\n\n用户问题：{question}"},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    answer = response.choices[0].message.content or ""

    sources = []
    if db:
        for hit in hits:
            doc = db.query(Document).filter(Document.id == hit.get("document_id")).first()
            sources.append({
                "text": hit.get("chunk_text", "")[:200],
                "document_name": doc.original_filename if doc else "未知",
                "chunk_index": hit.get("chunk_index", 0),
                "score": hit.get("score", 0),
                "metadata": hit.get("metadata"),
            })

    return {"answer": answer, "sources": sources}


async def rag_query_stream(
    question: str,
    knowledge_base_ids: List[int],
    domain_id: int = None,
    top_k: int = 5,
    db: Session = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    hits = retrieve_context(question, knowledge_base_ids, top_k)
    context = build_context_text(hits)
    system_prompt = get_system_prompt(domain_id, db)

    sources = []
    if db:
        for hit in hits:
            doc = db.query(Document).filter(Document.id == hit.get("document_id")).first()
            sources.append({
                "text": hit.get("chunk_text", "")[:200],
                "document_name": doc.original_filename if doc else "未知",
                "chunk_index": hit.get("chunk_index", 0),
                "score": hit.get("score", 0),
                "metadata": hit.get("metadata"),
            })

    yield {"type": "sources", "data": {"sources": sources}}

    client = get_llm_client()
    stream = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"上下文信息：\n{context}\n\n用户问题：{question}"},
        ],
        temperature=0.3,
        max_tokens=2000,
        stream=True,
    )

    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield {
                "type": "token",
                "data": {"content": chunk.choices[0].delta.content},
            }

    yield {"type": "done", "data": {}}
