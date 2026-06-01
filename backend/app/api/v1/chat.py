from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import json
from sse_starlette.sse import EventSourceResponse
from app.database import get_db
from app.models.user import User
from app.schemas.knowledge import ChatRequest
from app.core.deps import get_current_user
from app.services.rag_chain import rag_query, rag_query_stream

router = APIRouter(prefix="/chat", tags=["智能问答"])


@router.post("/query")
async def chat_query(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await rag_query(
        question=request.question,
        knowledge_base_ids=request.knowledge_base_ids,
        domain_id=request.domain_id,
        top_k=request.top_k,
        db=db,
    )
    return result


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    async def event_generator():
        async for event in rag_query_stream(
            question=request.question,
            knowledge_base_ids=request.knowledge_base_ids,
            domain_id=request.domain_id,
            top_k=request.top_k,
            db=db,
        ):
            yield {"event": event["type"], "data": json.dumps(event["data"], ensure_ascii=False)}

    return EventSourceResponse(event_generator())
