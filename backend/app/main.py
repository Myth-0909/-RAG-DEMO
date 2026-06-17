import os

# Bypass system HTTP proxy for internal-network services.
# The host machine has http_proxy set, which would route all requests through
# a local proxy that cannot reach internal IPs (172.16.x.x). Both httpx and
# gRPC respect http_proxy, so we must exclude internal subnets from proxying.
# Service files already use trust_env=False for httpx; this covers gRPC/Milvus
# and acts as a belt-and-suspenders safety net.
_NO_PROXY_HOSTS = (
    "localhost,127.0.0.1,172.16.0.0/16,10.0.0.0/8,192.168.0.0/16,.local"
)
for _key in ("no_proxy", "NO_PROXY"):
    _existing = os.environ.get(_key, "")
    if _existing:
        os.environ[_key] = f"{_existing},{_NO_PROXY_HOSTS}"
    else:
        os.environ[_key] = _NO_PROXY_HOSTS

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
import app.models  # noqa: F401 — ensure all models loaded before mapper config
from app.api.v1 import auth, roles, knowledge, chat, domains, conversations, model_configs, processing_tasks
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(roles.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(domains.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(model_configs.router, prefix="/api/v1")
app.include_router(processing_tasks.router, prefix="/api/v1")


@app.on_event("startup")
async def ensure_fts_index():
    """Ensure FTS5 BM25 index exists and is populated on startup."""
    try:
        from app.database import SessionLocal
        from app.services.bm25_service import BM25Service
        from app.models.knowledge import DocumentChunk

        db = SessionLocal()
        try:
            bm25 = BM25Service(db)
            if not bm25.table_exists():
                logger.info("FTS5 table does not exist — skipping auto-index")
                return

            indexed = bm25.chunk_count()
            if indexed > 0:
                logger.info(f"FTS5 index already populated: {indexed} chunks")
                return

            # Check if there are chunks to index
            total = db.query(DocumentChunk).count()
            if total == 0:
                logger.info("No document chunks to index")
                return

            logger.info(f"FTS5 index is empty, auto-rebuilding for {total} chunks...")
            bm25.rebuild_index()
            db.commit()
            logger.info(f"FTS5 auto-rebuild complete: {total} chunks indexed")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"FTS5 startup check failed (non-fatal): {e}")


@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME}
