from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import os
import uuid
from app.database import get_db
from app.models.user import User
from app.models.knowledge import KnowledgeBase, Document, DocumentChunk
from app.schemas.knowledge import (
    KnowledgeBaseCreate, KnowledgeBaseUpdate, KnowledgeBaseResponse,
    DocumentResponse, ChunkResponse,
)
from app.core.deps import get_current_user, require_permission
from app.services.document import process_document

router = APIRouter(prefix="/knowledge", tags=["知识库管理"])


@router.get("/", response_model=List[KnowledgeBaseResponse])
def list_knowledge_bases(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    kbs = db.query(KnowledgeBase).offset(skip).limit(limit).all()
    result = []
    for kb in kbs:
        resp = KnowledgeBaseResponse.model_validate(kb)
        resp.document_count = len(kb.documents)
        result.append(resp)
    return result


@router.post("/", response_model=KnowledgeBaseResponse)
def create_knowledge_base(
    kb_in: KnowledgeBaseCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    kb = KnowledgeBase(**kb_in.model_dump())
    db.add(kb)
    db.commit()
    db.refresh(kb)

    from app.services.milvus_service import MilvusService
    milvus = MilvusService()
    milvus.create_collection(f"kb_{kb.id}")

    return KnowledgeBaseResponse.model_validate(kb)


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
def get_knowledge_base(
    kb_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    resp = KnowledgeBaseResponse.model_validate(kb)
    resp.document_count = len(kb.documents)
    return resp


@router.put("/{kb_id}", response_model=KnowledgeBaseResponse)
def update_knowledge_base(
    kb_id: int,
    kb_in: KnowledgeBaseUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    for key, value in kb_in.model_dump(exclude_unset=True).items():
        setattr(kb, key, value)

    db.commit()
    db.refresh(kb)
    resp = KnowledgeBaseResponse.model_validate(kb)
    resp.document_count = len(kb.documents)
    return resp


@router.delete("/{kb_id}")
def delete_knowledge_base(
    kb_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    from app.services.milvus_service import MilvusService
    milvus = MilvusService()
    milvus.drop_collection(f"kb_{kb.id}")

    db.delete(kb)
    db.commit()
    return {"detail": "删除成功"}


# --- Documents ---
@router.get("/{kb_id}/documents", response_model=List[DocumentResponse])
def list_documents(
    kb_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    docs = db.query(Document).filter(Document.knowledge_base_id == kb_id).all()
    return docs


@router.post("/{kb_id}/documents", response_model=DocumentResponse)
async def upload_document(
    kb_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    metadata_json: Optional[str] = Form(None),
    chunk_strategy: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in [".pdf", ".docx", ".txt", ".md"]:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {file_ext}")

    filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join("uploads", filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    metadata = json.loads(metadata_json) if metadata_json else None
    strategy = chunk_strategy or kb.chunk_strategy

    doc = Document(
        knowledge_base_id=kb_id,
        filename=filename,
        original_filename=file.filename,
        file_type=file_ext.lstrip("."),
        file_size=len(content),
        status="pending",
        metadata_json=metadata,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(process_document, doc.id, file_path, strategy, metadata)

    return doc


@router.get("/{kb_id}/documents/{doc_id}", response_model=DocumentResponse)
def get_document(
    kb_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(
        Document.id == doc_id, Document.knowledge_base_id == kb_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


@router.delete("/{kb_id}/documents/{doc_id}")
def delete_document(
    kb_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(
        Document.id == doc_id, Document.knowledge_base_id == kb_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    from app.services.milvus_service import MilvusService
    milvus = MilvusService()
    milvus.delete_by_document(f"kb_{kb_id}", doc_id)

    file_path = os.path.join("uploads", doc.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.delete(doc)
    db.commit()
    return {"detail": "删除成功"}


@router.get("/{kb_id}/documents/{doc_id}/chunks", response_model=List[ChunkResponse])
def list_chunks(
    kb_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).all()
    return chunks
