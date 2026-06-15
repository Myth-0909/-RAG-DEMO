from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "RAG Knowledge Base"
    APP_ENV: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str = "sqlite:///./rag_system.db"

    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    MILVUS_HOST: str = "172.16.0.44"
    MILVUS_PORT: int = 19530
    MILVUS_DATABASE: str = "ljl_test"

    EMBEDDING_BASE_URL: str = "http://172.16.76.112:8001/v1"
    EMBEDDING_API_KEY: str = "sk-4f8a7b2c9d1e6f3a5b8c2d7e9f4a6b3c"
    EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-8B"
    EMBEDDING_DIM: int = 1024

    LLM_BASE_URL: str = "http://172.16.76.112:8001/v1"
    LLM_API_KEY: str = "sk-4f8a7b2c9d1e6f3a5b8c2d7e9f4a6b3c"
    LLM_MODEL: str = "Qwen/Qwen3-Embedding-8B"

    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 100

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
