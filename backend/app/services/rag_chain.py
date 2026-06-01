from typing import List, Dict, Any, AsyncGenerator, Optional
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


def build_system_prompt(
    domain_id: Optional[int] = None,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    base_prompt = """你是一个专业的知识库问答助手。请根据提供的上下文信息和对话历史回答用户的问题。

规则：
1. 仅基于提供的上下文信息回答，不要编造信息
2. 如果上下文中没有相关信息，请明确告知用户
3. 回答时引用来源编号，如 [1]、[2]
4. 保持回答简洁、准确、专业
5. 参考对话历史，理解用户的上下文意图"""

    if chat_history:
        base_prompt += "\n6. 如果用户的问题涉及之前的对话内容，请参考对话历史进行回答"

    return base_prompt


def build_chat_history_text(chat_history: List[Dict[str, str]] = None, max_turns: int = 5) -> str:
    """构建对话历史文本"""
    if not chat_history:
        return ""

    # 只取最近的几轮对话
    recent_history = chat_history[-max_turns * 2:]  # 每轮包含 user + assistant

    parts = []
    for msg in recent_history:
        role = "用户" if msg["role"] == "user" else "助手"
        parts.append(f"{role}: {msg['content']}")

    return "\n".join(parts)


async def rag_query(
    question: str,
    knowledge_base_ids: List[int],
    domain_id: int = None,
    top_k: int = 5,
    db: Session = None,
    chat_history: List[Dict[str, str]] = None,
    memory_context: str = "",
) -> Dict[str, Any]:
    # 检索知识库上下文
    kb_context = retrieve_context(question, knowledge_base_ids, top_k)
    kb_context_text = build_context_text(kb_context)

    # 构建系统提示
    system_prompt = build_system_prompt(domain_id, chat_history)

    # 构建完整上下文
    full_context_parts = []
    if memory_context:
        full_context_parts.append(memory_context)
    if kb_context_text:
        full_context_parts.append(kb_context_text)

    full_context = "\n\n".join(full_context_parts)

    # 构建消息
    messages = [
        {"role": "system", "content": system_prompt},
    ]

    # 添加对话历史
    if chat_history:
        for msg in chat_history[-10:]:  # 最近5轮对话
            messages.append({"role": msg["role"], "content": msg["content"]})

    # 添加当前问题（包含上下文）
    user_content = question
    if full_context:
        user_content = f"{full_context}\n\n用户问题：{question}"

    messages.append({"role": "user", "content": user_content})

    # 调用 LLM
    client = get_llm_client()
    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=2000,
    )

    answer = response.choices[0].message.content

    # 构建来源信息
    sources = []
    for hit in kb_context:
        doc = db.query(Document).filter(Document.id == hit["document_id"]).first() if db else None
        sources.append({
            "document_name": doc.original_filename if doc else "Unknown",
            "chunk_index": hit["chunk_index"],
            "score": hit["score"],
            "text": hit["chunk_text"][:200] + "..." if len(hit["chunk_text"]) > 200 else hit["chunk_text"],
        })

    return {
        "answer": answer,
        "sources": sources,
    }


async def rag_query_stream(
    question: str,
    knowledge_base_ids: List[int],
    domain_id: int = None,
    top_k: int = 5,
    db: Session = None,
    chat_history: List[Dict[str, str]] = None,
    memory_context: str = "",
) -> AsyncGenerator[Dict[str, Any], None]:
    hits = retrieve_context(question, knowledge_base_ids, top_k)
    context = build_context_text(hits)
    system_prompt = build_system_prompt(domain_id, chat_history)

    # 构建对话历史
    history_text = build_chat_history_text(chat_history)

    # 构建用户消息
    user_message_parts = []
    if memory_context:
        user_message_parts.append(memory_context)
    if history_text:
        user_message_parts.append(f"对话历史：\n{history_text}")
    user_message_parts.append(f"上下文信息：\n{context}")
    user_message_parts.append(f"用户问题：{question}")

    user_message = "\n\n".join(user_message_parts)

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
            {"role": "user", "content": user_message},
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
