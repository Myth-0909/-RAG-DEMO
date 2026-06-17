import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

from sqlalchemy.exc import OperationalError

from app.database import SessionLocal as _SessionLocal
from app.config import settings
from app.models.processing_task import ProcessingTask
from app.services.document import process_document_stream

logger = logging.getLogger(__name__)

_MAX_DB_RETRIES = 5
_DB_RETRY_DELAY = 1.0  # seconds


def _safe_commit(db, context: str = ""):
    """Commit with retry on transient SQLite lock errors."""
    for attempt in range(_MAX_DB_RETRIES):
        try:
            db.commit()
            return
        except OperationalError as e:
            if "database is locked" in str(e) and attempt < _MAX_DB_RETRIES - 1:
                logger.debug(f"DB locked during {context}, retry {attempt + 1}/{_MAX_DB_RETRIES}")
                time.sleep(_DB_RETRY_DELAY)
                db.rollback()  # Reset transaction state before retry
                continue
            raise

STEP_LABELS = {
    "convert": "文档转换",
    "extract": "文本提取",
    "clean": "清洗评估",
    "apply": "执行清洗",
    "analyze": "内容分析",
    "chunk": "智能分块",
    "refine": "分块精炼",
    "embed": "向量化存储",
    "complete": "处理完成",
    "error": "处理错误",
}


async def run_background_processing(
    task_id: int,
    doc_id: int,
    file_path: str,
    metadata: Optional[dict] = None,
):
    db = _SessionLocal()
    try:
        task = db.query(ProcessingTask).filter(ProcessingTask.id == task_id).first()
        if not task:
            logger.error(f"ProcessingTask {task_id} not found")
            return

        task.status = "processing"
        task.current_step = "convert"
        _safe_commit(db, f"step={task.current_step}")

        collected_events = []

        async for event in process_document_stream(doc_id, file_path, metadata):
            step = event.get("step", "")
            status = event.get("status", "")
            data = event.get("data", {})

            enriched_event = {
                **event,
                "step_label": STEP_LABELS.get(step, step),
                "timestamp": datetime.now().isoformat(),
            }

            if status == "thinking" and "token" not in data:
                collected_events.append(enriched_event)
            elif status in ("done", "error"):
                collected_events.append(enriched_event)

            task.current_step = step if status != "done" else step
            task.events = list(collected_events)
            _safe_commit(db, f"step={task.current_step}")

        task = db.query(ProcessingTask).filter(ProcessingTask.id == task_id).first()
        if task:
            last_event = collected_events[-1] if collected_events else {}
            if last_event.get("step") == "complete":
                task.status = "completed"
                task.result_summary = last_event.get("data", {})
            elif last_event.get("step") == "error" or last_event.get("status") == "error":
                task.status = "failed"
                task.error_message = last_event.get("data", {}).get("message", "未知错误")
            else:
                task.status = "completed"
            task.current_step = "complete" if task.status == "completed" else "error"
            task.events = collected_events
            _safe_commit(db, f"step={task.current_step}")

        logger.info(f"Background processing completed for task {task_id}, doc {doc_id}")

    except Exception as e:
        logger.exception(f"Background processing failed for task {task_id}")
        try:
            task = db.query(ProcessingTask).filter(ProcessingTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)[:500]
                task.current_step = "error"
                _safe_commit(db, f"step={task.current_step}")
        except Exception:
            pass
    finally:
        db.close()


def start_background_processing(
    task_id: int,
    doc_id: int,
    file_path: str,
    metadata: Optional[dict] = None,
):
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.ensure_future(
            run_background_processing(task_id, doc_id, file_path, metadata)
        )
    else:
        loop.run_until_complete(
            run_background_processing(task_id, doc_id, file_path, metadata)
        )
