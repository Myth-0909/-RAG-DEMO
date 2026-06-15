from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from sse_starlette.sse import EventSourceResponse
from app.database import get_db
from app.models.user import User
from app.models.conversation import Conversation, ChatMessage
from app.schemas.knowledge import ChatRequest
from app.core.deps import get_current_user
from app.services.rag_chain import rag_query, rag_query_stream
from app.services.memory_service import retrieve_relevant_memories, build_memory_context, update_conversation_summary_on_message
from datetime import datetime

router = APIRouter(prefix="/chat", tags=["智能问答"])


def save_message(db: Session, conversation_id: int, role: str, content: str, sources: list = None):
    """保存消息到对话历史"""
    message = ChatMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        sources=sources
    )
    db.add(message)

    # 更新对话的更新时间
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conversation:
        conversation.updated_at = datetime.utcnow()

    db.commit()


def get_or_create_conversation(
    db: Session,
    user_id: int,
    conversation_id: int = None,
    knowledge_base_ids: list = None,
    domain_id: int = None,
    question: str = None
) -> Conversation:
    """获取或创建对话"""
    if conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="对话不存在")
        return conversation

    # 创建新对话，使用问题前20个字符作为标题
    title = question[:20] + "..." if len(question) > 20 else question
    conversation = Conversation(
        user_id=user_id,
        title=title,
        knowledge_base_ids=knowledge_base_ids or [],
        domain_id=domain_id
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.post("/query")
async def chat_query(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 获取或创建对话
    conversation = get_or_create_conversation(
        db=db,
        user_id=current_user.id,
        conversation_id=request.conversation_id,
        knowledge_base_ids=request.knowledge_base_ids,
        domain_id=request.domain_id,
        question=request.question
    )

    # 保存用户消息
    save_message(db, conversation.id, "user", request.question)

    # 获取对话历史
    chat_history = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation.id
    ).order_by(ChatMessage.created_at.asc()).all()

    # 构建历史消息列表（用于 RAG）
    history_messages = [
        {"role": msg.role, "content": msg.content}
        for msg in chat_history[:-1]  # 不包含刚保存的用户消息，因为已经在 question 中
    ]

    # 检索长期记忆（相关历史对话）
    memories = retrieve_relevant_memories(
        db=db,
        user_id=current_user.id,
        query=request.question,
        top_k=3
    )
    memory_context = build_memory_context(memories)

    # 执行 RAG 查询
    result = await rag_query(
        question=request.question,
        knowledge_base_ids=request.knowledge_base_ids,
        domain_id=request.domain_id,
        top_k=request.top_k,
        db=db,
        chat_history=history_messages,
        memory_context=memory_context
    )

    # 保存助手消息
    save_message(db, conversation.id, "assistant", result["answer"], result.get("sources"))

    # 更新对话摘要
    update_conversation_summary_on_message(db, conversation.id, current_user.id)

    # 返回结果，包含 conversation_id
    return {
        "conversation_id": conversation.id,
        "answer": result["answer"],
        "sources": result["sources"]
    }


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 获取或创建对话
    conversation = get_or_create_conversation(
        db=db,
        user_id=current_user.id,
        conversation_id=request.conversation_id,
        knowledge_base_ids=request.knowledge_base_ids,
        domain_id=request.domain_id,
        question=request.question
    )

    # 保存用户消息
    save_message(db, conversation.id, "user", request.question)

    # 获取对话历史
    chat_history = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation.id
    ).order_by(ChatMessage.created_at.asc()).all()

    # 构建历史消息列表
    history_messages = [
        {"role": msg.role, "content": msg.content}
        for msg in chat_history[:-1]
    ]

    # 检索长期记忆
    memories = retrieve_relevant_memories(
        db=db,
        user_id=current_user.id,
        query=request.question,
        top_k=3
    )
    memory_context = build_memory_context(memories)

    full_answer = []

    async def event_generator():
        # 首先发送 conversation_id
        yield {"event": "conversation_id", "data": json.dumps({"conversation_id": conversation.id}, ensure_ascii=False)}

        async for event in rag_query_stream(
            question=request.question,
            knowledge_base_ids=request.knowledge_base_ids,
            domain_id=request.domain_id,
            top_k=request.top_k,
            db=db,
            chat_history=history_messages,
            memory_context=memory_context
        ):
            if event["type"] == "token":
                full_answer.append(event["data"]["content"])

            yield {"event": event["type"], "data": json.dumps(event["data"], ensure_ascii=False)}

        # 保存完整的助手回答
        save_message(db, conversation.id, "assistant", "".join(full_answer))

        # 更新对话摘要
        update_conversation_summary_on_message(db, conversation.id, current_user.id)

    return EventSourceResponse(event_generator())
