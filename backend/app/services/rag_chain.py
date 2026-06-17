from typing import List, Dict, Any, AsyncGenerator, Optional
from sqlalchemy.orm import Session
from app.services.milvus_service import MilvusService
from app.services.embedding import embed_query
from app.services.model_config_service import get_current_llm_config
from app.models.knowledge import KnowledgeBase, Document, Domain
from app.config import settings
from openai import OpenAI
import httpx
import logging

logger = logging.getLogger(__name__)

# RRF (Reciprocal Rank Fusion) constant
RRF_K = 60


def get_llm_client():
    """Get LLM client using current active config (DB or .env fallback).

    Uses trust_env=False to bypass system HTTP_PROXY settings, which would
    otherwise route internal-network requests through an external proxy and
    cause 502 errors.
    """
    cfg = get_current_llm_config()
    http_client = httpx.Client(transport=httpx.HTTPTransport(trust_env=False))
    return OpenAI(base_url=cfg.base_url, api_key=cfg.api_key, http_client=http_client)


def get_current_model_name() -> str:
    cfg = get_current_llm_config()
    return cfg.model_name


def _rrf_merge(
    vector_results: List[Dict[str, Any]],
    bm25_results: List[Dict[str, Any]],
    k: int = RRF_K,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Merge two ranked lists using Reciprocal Rank Fusion.

    score(d) = sum_{r in rankings} 1 / (k + rank_r(d))

    Uses (document_id, chunk_index) as the unique key to match chunks
    across the two search methods, since they use different ID systems.
    """
    if not vector_results:
        return bm25_results[:top_k]
    if not bm25_results:
        return vector_results[:top_k]

    def _make_key(hit: Dict) -> str:
        return f"{hit.get('document_id', 0)}:{hit.get('chunk_index', 0)}"

    # Build rank maps: key -> rank position (1-indexed)
    vector_ranks = {}
    id_to_item = {}
    for i, r in enumerate(vector_results):
        key = _make_key(r)
        vector_ranks[key] = i + 1
        id_to_item[key] = r

    bm25_ranks = {}
    for i, r in enumerate(bm25_results):
        key = _make_key(r)
        bm25_ranks[key] = i + 1
        if key not in id_to_item:
            id_to_item[key] = r

    # Default rank for missing items
    v_default = len(vector_results) + 1
    b_default = len(bm25_results) + 1

    all_keys = set(vector_ranks.keys()) | set(bm25_ranks.keys())

    scored = []
    for key in all_keys:
        rrf = (
            1.0 / (k + vector_ranks.get(key, v_default))
            + 1.0 / (k + bm25_ranks.get(key, b_default))
        )
        scored.append((key, rrf))

    scored.sort(key=lambda x: x[1], reverse=True)

    merged = []
    for key, rrf_score in scored[:top_k]:
        item = dict(id_to_item[key])
        item["score"] = round(rrf_score, 4)
        merged.append(item)

    return merged


def retrieve_context(
    question: str,
    knowledge_base_ids: List[int],
    top_k: int = 5,
    search_mode: str = "hybrid",
    db: Optional[Session] = None,
) -> List[Dict[str, Any]]:
    """Retrieve context from knowledge bases using the specified search mode.

    Args:
        question: User's question.
        knowledge_base_ids: List of KB IDs to search across.
        top_k: Number of top results to return.
        search_mode: "vector", "keyword", or "hybrid" (default).
        db: SQLAlchemy Session (required for keyword/hybrid modes).

    Returns:
        List of hit dicts with keys matching MilvusService.search().
    """
    valid_modes = ("vector", "keyword", "hybrid")
    if search_mode not in valid_modes:
        logger.warning(f"Invalid search_mode '{search_mode}', falling back to hybrid")
        search_mode = "hybrid"

    # ── Vector search ─────────────────────────────────────────────────
    def _vector_search(k: int) -> List[Dict]:
        query_embedding = embed_query(question)
        milvus = MilvusService()
        all_hits = []
        for kb_id in knowledge_base_ids:
            collection_name = f"kb_{kb_id}"
            try:
                hits = milvus.search(
                    collection_name=collection_name,
                    query_embedding=query_embedding,
                    top_k=k,
                )
                for hit in hits:
                    hit["knowledge_base_id"] = kb_id
                all_hits.extend(hits)
            except Exception as e:
                logger.warning(f"Vector search failed for {collection_name}: {e}")
        all_hits.sort(key=lambda x: x["score"], reverse=True)
        return all_hits[:k]

    # ── BM25 search ───────────────────────────────────────────────────
    def _bm25_search(k: int) -> List[Dict]:
        try:
            from app.services.bm25_service import BM25Service
            bm25 = BM25Service(db)
            return bm25.search(question, knowledge_base_ids, top_k=k)
        except Exception as e:
            logger.warning(f"BM25 search failed: {e}")
            return []

    # ── Route by mode ─────────────────────────────────────────────────
    if search_mode == "vector":
        return _vector_search(top_k)

    if search_mode == "keyword":
        if db is None:
            logger.warning("keyword mode requires db session, falling back to vector")
            return _vector_search(top_k)
        bm25_results = _bm25_search(top_k)
        if not bm25_results:
            logger.info("BM25 returned no results, falling back to vector search")
            return _vector_search(top_k)
        return bm25_results

    # search_mode == "hybrid"
    if db is None:
        logger.warning("hybrid mode requires db session, falling back to vector-only")
        return _vector_search(top_k)

    # Oversample each method and merge with RRF
    oversample_k = top_k * 3
    vector_results = _vector_search(oversample_k)
    bm25_results = _bm25_search(oversample_k)

    if not bm25_results:
        return vector_results[:top_k]

    return _rrf_merge(vector_results, bm25_results, k=RRF_K, top_k=top_k)


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
    search_mode: str = "hybrid",
) -> Dict[str, Any]:
    # 检索知识库上下文
    kb_context = retrieve_context(
        question, knowledge_base_ids, top_k,
        search_mode=search_mode, db=db,
    )
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
        model=get_current_model_name(),
        messages=messages,
        temperature=0.3,
        max_tokens=2000,
    )

    answer = response.choices[0].message.content

    # 构建来源信息
    sources = []
    for hit in kb_context:
        doc = db.query(Document).filter(Document.id == hit["document_id"]).first() if db else None
        chunk_text = hit.get("chunk_text", "")
        sources.append({
            "document_name": doc.original_filename if doc else "Unknown",
            "document_id": hit.get("document_id", 0),
            "chunk_index": hit.get("chunk_index", 0),
            "score": hit.get("score", 0),
            "text": chunk_text,
            "metadata": hit.get("metadata", {}),
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
    search_mode: str = "hybrid",
) -> AsyncGenerator[Dict[str, Any], None]:
    hits = retrieve_context(
        question, knowledge_base_ids, top_k,
        search_mode=search_mode, db=db,
    )
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
                "text": hit.get("chunk_text", ""),
                "document_name": doc.original_filename if doc else "未知",
                "document_id": hit.get("document_id", 0),
                "chunk_index": hit.get("chunk_index", 0),
                "score": hit.get("score", 0),
                "metadata": hit.get("metadata"),
            })

    yield {"type": "sources", "data": {"sources": sources}}

    client = get_llm_client()
    stream = client.chat.completions.create(
        model=get_current_model_name(),
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
