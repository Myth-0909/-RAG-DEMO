from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func
from app.database import Base


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    base_url = Column(String(500), nullable=False)
    model_name = Column(String(200), nullable=False)
    api_key = Column(String(500), nullable=False)
    config_type = Column(String(50), default="llm")  # llm, embedding
    is_active = Column(Boolean, default=True)
    is_current = Column(Boolean, default=False)  # 当前正在使用的配置（每种 type 最多一个）
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ModelConfigHistory(Base):
    __tablename__ = "model_config_history"

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, nullable=False)
    action = Column(String(20), nullable=False)  # created, updated, deleted, restored
    name = Column(String(100), nullable=False)
    base_url = Column(String(500), nullable=False)
    model_name = Column(String(200), nullable=False)
    api_key = Column(String(500), nullable=False)
    config_type = Column(String(50), default="llm")
    changed_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
