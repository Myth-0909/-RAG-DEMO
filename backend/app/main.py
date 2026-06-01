from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
import app.models  # noqa: F401 — ensure all models loaded before mapper config
from app.api.v1 import auth, roles, knowledge, chat, domains

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


@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME}
