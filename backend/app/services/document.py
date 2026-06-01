from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.models.knowledge import Document, DocumentChunk
from app.services.chunking import chunk_text
from app.services.embedding import embed_texts
from app.services.milvus_service import MilvusService
import os
import logging

logger = logging.getLogger(__name__)

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

_engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def extract_text(file_path: str, file_type: str) -> str:
    if file_type == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)

    elif file_type == "docx":
        from docx import Document as DocxDocument
        doc = DocxDocument(file_path)
        return "\n\n".join([para.text for para in doc.paragraphs if para.text.strip()])

    elif file_type in ("txt", "md"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    else:
        raise ValueError(f"不支持的文件类型: {file_type}")


def process_document(doc_id: int, file_path: str, strategy: str, metadata: dict = None):
    db = _SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            logger.error(f"Document {doc_id} not found")
            return

        doc.status = "processing"
        db.commit()

        text = extract_text(file_path, doc.file_type)
        if not text.strip():
            doc.status = "failed"
            doc.error_message = "文档内容为空"
            db.commit()
            return

        chunks = chunk_text(text, strategy=strategy, metadata=metadata)
        if not chunks:
            doc.status = "failed"
            doc.error_message = "分块结果为空"
            db.commit()
            return

        collection_name = f"kb_{doc.knowledge_base_id}"
        milvus = MilvusService()
        milvus.create_collection(collection_name)

        batch_size = 50
        all_milvus_ids = []

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c.text for c in batch]
            embeddings = embed_texts(texts)

            milvus_ids = milvus.insert(
                collection_name=collection_name,
                embeddings=embeddings,
                chunk_texts=texts,
                parent_texts=[c.parent_text for c in batch],
                metadata_list=[c.metadata for c in batch],
                document_ids=[doc_id] * len(batch),
                chunk_indices=[c.chunk_index for c in batch],
            )
            all_milvus_ids.extend(milvus_ids)

            for j, chunk in enumerate(batch):
                db_chunk = DocumentChunk(
                    document_id=doc_id,
                    chunk_index=chunk.chunk_index,
                    chunk_text=chunk.text,
                    parent_text=chunk.parent_text,
                    metadata_json=chunk.metadata,
                    milvus_id=str(all_milvus_ids[i + j]) if i + j < len(all_milvus_ids) else None,
                    token_count=len(chunk.text),
                )
                db.add(db_chunk)

        doc.status = "completed"
        doc.chunk_count = len(chunks)
        db.commit()
        logger.info(f"Document {doc_id} processed: {len(chunks)} chunks")

    except Exception as e:
        logger.exception(f"Error processing document {doc_id}")
        doc.status = "failed"
        doc.error_message = str(e)[:500]
        db.commit()
    finally:
        db.close()
