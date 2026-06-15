from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.user import User
from app.models.processing_task import ProcessingTask
from app.models.knowledge import KnowledgeBase, Document
from app.schemas.processing_task import ProcessingTaskResponse, ProcessingTaskListResponse
from app.core.deps import get_current_user

router = APIRouter(prefix="/processing-tasks", tags=["处理任务"])


@router.get("/", response_model=List[ProcessingTaskListResponse])
def list_processing_tasks(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = db.query(ProcessingTask)
    if status:
        query = query.filter(ProcessingTask.status == status)
    tasks = query.order_by(ProcessingTask.created_at.desc()).offset(skip).limit(limit).all()

    result = []
    for task in tasks:
        doc = db.query(Document).filter(Document.id == task.document_id).first()
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == task.knowledge_base_id).first()
        resp = ProcessingTaskListResponse(
            id=task.id,
            document_id=task.document_id,
            knowledge_base_id=task.knowledge_base_id,
            status=task.status,
            current_step=task.current_step,
            error_message=task.error_message,
            document_name=doc.original_filename if doc else None,
            knowledge_base_name=kb.name if kb else None,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        result.append(resp)
    return result


@router.get("/{task_id}", response_model=ProcessingTaskResponse)
def get_processing_task(
    task_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    task = db.query(ProcessingTask).filter(ProcessingTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    doc = db.query(Document).filter(Document.id == task.document_id).first()
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == task.knowledge_base_id).first()

    return ProcessingTaskResponse(
        id=task.id,
        document_id=task.document_id,
        knowledge_base_id=task.knowledge_base_id,
        status=task.status,
        current_step=task.current_step,
        events=task.events or [],
        error_message=task.error_message,
        result_summary=task.result_summary,
        document_name=doc.original_filename if doc else None,
        knowledge_base_name=kb.name if kb else None,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.post("/{task_id}/retry")
def retry_processing_task(
    task_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    task = db.query(ProcessingTask).filter(ProcessingTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "failed":
        raise HTTPException(status_code=400, detail="只能重试失败的任务")

    doc = db.query(Document).filter(Document.id == task.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    import os
    file_path = os.path.join("uploads", doc.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=400, detail="文件不存在")

    doc.status = "pending"
    task.status = "pending"
    task.events = []
    task.error_message = None
    task.current_step = None
    task.result_summary = None
    db.commit()

    from app.services.background_processor import start_background_processing
    start_background_processing(
        task_id=task.id,
        doc_id=doc.id,
        file_path=file_path,
        metadata=doc.metadata_json or {},
    )

    return {"detail": "已重新启动处理"}
