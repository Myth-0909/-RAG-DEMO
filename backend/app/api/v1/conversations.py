"""对话管理 API"""
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.conversation import Conversation, ChatMessage
from app.models.user import User
from app.core.deps import get_current_user

router = APIRouter(prefix="/conversations", tags=["对话管理"])


# ============ Pydantic Models ============

class ConversationCreate(BaseModel):
    title: str
    knowledge_base_ids: List[int] = []
    domain_id: int | None = None


class ConversationResponse(BaseModel):
    id: int
    title: str
    knowledge_base_ids: List[int] | None
    domain_id: int | None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    sources: list | None
    created_at: datetime

    class Config:
        from_attributes = True


# ============ API Endpoints ============

@router.get("/", response_model=List[ConversationResponse])
def list_conversations(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的所有对话"""
    conversations = db.query(Conversation).filter(
        Conversation.user_id == current_user.id
    ).order_by(Conversation.updated_at.desc()).offset(skip).limit(limit).all()

    result = []
    for conv in conversations:
        message_count = len(conv.messages)
        conv_dict = {
            "id": conv.id,
            "title": conv.title,
            "knowledge_base_ids": conv.knowledge_base_ids,
            "domain_id": conv.domain_id,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
            "message_count": message_count
        }
        result.append(conv_dict)
    
    return result


@router.post("/", response_model=ConversationResponse)
def create_conversation(
    data: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新对话"""
    conversation = Conversation(
        user_id=current_user.id,
        title=data.title,
        knowledge_base_ids=data.knowledge_base_ids,
        domain_id=data.domain_id
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        knowledge_base_ids=conversation.knowledge_base_ids,
        domain_id=conversation.domain_id,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=0
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取单个对话详情"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    
    message_count = len(conversation.messages)
    
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        knowledge_base_ids=conversation.knowledge_base_ids,
        domain_id=conversation.domain_id,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=message_count
    )


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
def get_conversation_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取对话的所有消息"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    
    return conversation.messages


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除对话"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    
    db.delete(conversation)
    db.commit()
    
    return {"message": "对话已删除"}
