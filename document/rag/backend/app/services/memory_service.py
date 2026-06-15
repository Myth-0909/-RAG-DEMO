"""用户长期记忆服务：对话摘要生成、向量化和检索"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.models.conversation import Conversation, ChatMessage, ConversationSummary
from app.services.embedding import embed_texts, embed_query
from app.config import settings

logger = logging.getLogger(__name__)


def generate_conversation_summary(messages: List[Dict[str, str]]) -> str:
    """生成对话摘要"""
    if not messages:
        return ""
    
    # 简单摘要：提取用户问题和助手回答的关键点
    user_questions = [m["content"] for m in messages if m["role"] == "user"]
    assistant_answers = [m["content"] for m in messages if m["role"] == "assistant"]
    
    summary_parts = []
    if user_questions:
        summary_parts.append("用户讨论的主题：" + "；".join(user_questions[:3]))
    if assistant_answers:
        # 只取前100个字符作为摘要
        key_points = [a[:100] for a in assistant_answers[:3]]
        summary_parts.append("关键信息：" + "；".join(key_points))
    
    return " | ".join(summary_parts)


def save_conversation_summary(
    db: Session,
    user_id: int,
    conversation_id: int,
    summary: str,
) -> Optional[ConversationSummary]:
    """保存对话摘要并生成向量"""
    if not summary.strip():
        return None
    
    try:
        # 生成摘要的向量
        embedding = embed_texts([summary])[0]
        
        # 检查是否已存在该对话的摘要
        existing = db.query(ConversationSummary).filter(
            ConversationSummary.conversation_id == conversation_id
        ).first()
        
        if existing:
            existing.summary = summary
            existing.embedding = embedding
            db.commit()
            db.refresh(existing)
            return existing
        
        # 创建新的摘要记录
        cs = ConversationSummary(
            user_id=user_id,
            conversation_id=conversation_id,
            summary=summary,
            embedding=embedding,
        )
        db.add(cs)
        db.commit()
        db.refresh(cs)
        return cs
    except Exception as e:
        logger.error(f"Failed to save conversation summary: {e}")
        db.rollback()
        return None


def retrieve_relevant_memories(
    db: Session,
    user_id: int,
    query: str,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """检索与当前查询相关的历史对话摘要"""
    try:
        # 获取该用户的所有对话摘要
        summaries = db.query(ConversationSummary).filter(
            ConversationSummary.user_id == user_id
        ).all()
        
        if not summaries:
            return []
        
        # 对查询进行向量化
        query_embedding = embed_query(query)
        
        # 计算相似度并排序
        scored_memories = []
        for summary in summaries:
            if not summary.embedding:
                continue
            
            similarity = _cosine_similarity(query_embedding, summary.embedding)
            scored_memories.append({
                "summary": summary.summary,
                "conversation_id": summary.conversation_id,
                "similarity": similarity,
                "created_at": summary.created_at,
            })
        
        # 按相似度排序并返回 top_k
        scored_memories.sort(key=lambda x: x["similarity"], reverse=True)
        return scored_memories[:top_k]
    except Exception as e:
        logger.error(f"Failed to retrieve memories: {e}")
        return []


def build_memory_context(memories: List[Dict[str, Any]]) -> str:
    """构建记忆上下文文本"""
    if not memories:
        return ""
    
    parts = ["【相关历史对话】"]
    for i, mem in enumerate(memories, 1):
        parts.append(f"{i}. {mem['summary']} (相关度: {mem['similarity']:.2f})")
    
    return "\n".join(parts)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """计算余弦相似度"""
    if len(a) != len(b):
        return 0.0
    
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot / (norm_a * norm_b)


def update_conversation_summary_on_message(
    db: Session,
    conversation_id: int,
    user_id: int,
):
    """在对话更新时重新生成摘要"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()
    
    if not conversation:
        return
    
    # 获取对话的所有消息
    messages = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation_id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    # 转换为字典列表
    msg_list = [{"role": m.role, "content": m.content} for m in messages]
    
    # 生成摘要
    summary = generate_conversation_summary(msg_list)
    
    # 保存摘要
    if summary:
        save_conversation_summary(db, user_id, conversation_id, summary)
