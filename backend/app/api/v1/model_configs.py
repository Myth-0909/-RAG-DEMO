from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.user import User
from app.models.model_config import ModelConfig, ModelConfigHistory
from app.schemas.model_config import (
    ModelConfigCreate, ModelConfigUpdate, ModelConfigResponse,
    ModelConfigHistoryResponse,
)
from app.core.deps import get_current_user, get_current_superuser

router = APIRouter(prefix="/model-configs", tags=["模型配置"])


def _record_history(
    db: Session, config: ModelConfig, action: str, changed_by: str = None
):
    history = ModelConfigHistory(
        config_id=config.id,
        action=action,
        name=config.name,
        base_url=config.base_url,
        model_name=config.model_name,
        api_key=config.api_key,
        config_type=config.config_type,
        changed_by=changed_by,
    )
    db.add(history)


@router.get("/", response_model=List[ModelConfigResponse])
def list_model_configs(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return db.query(ModelConfig).order_by(ModelConfig.created_at.desc()).all()


@router.post("/", response_model=ModelConfigResponse)
def create_model_config(
    config_in: ModelConfigCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_superuser),
):
    existing = db.query(ModelConfig).filter(ModelConfig.name == config_in.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"配置名称 '{config_in.name}' 已存在")

    config = ModelConfig(**config_in.model_dump())
    db.add(config)
    db.commit()
    db.refresh(config)

    _record_history(db, config, "created", user.username)
    db.commit()
    db.refresh(config)

    return config


@router.get("/{config_id}", response_model=ModelConfigResponse)
def get_model_config(
    config_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    config = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    return config


@router.put("/{config_id}", response_model=ModelConfigResponse)
def update_model_config(
    config_id: int,
    config_in: ModelConfigUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_superuser),
):
    config = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")

    update_data = config_in.model_dump(exclude_unset=True)
    if "name" in update_data:
        existing = db.query(ModelConfig).filter(
            ModelConfig.name == update_data["name"],
            ModelConfig.id != config_id,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"配置名称 '{update_data['name']}' 已存在")

    for key, value in update_data.items():
        setattr(config, key, value)

    db.commit()
    db.refresh(config)

    _record_history(db, config, "updated", user.username)
    db.commit()
    db.refresh(config)

    return config


@router.delete("/{config_id}")
def delete_model_config(
    config_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_superuser),
):
    config = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")

    _record_history(db, config, "deleted", user.username)
    db.delete(config)
    db.commit()

    return {"detail": "删除成功"}


@router.get("/{config_id}/history", response_model=List[ModelConfigHistoryResponse])
def get_config_history(
    config_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    config = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")

    return (
        db.query(ModelConfigHistory)
        .filter(ModelConfigHistory.config_id == config_id)
        .order_by(ModelConfigHistory.created_at.desc())
        .all()
    )


@router.get("/history/all", response_model=List[ModelConfigHistoryResponse])
def get_all_history(
    limit: int = 50,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return (
        db.query(ModelConfigHistory)
        .order_by(ModelConfigHistory.created_at.desc())
        .limit(limit)
        .all()
    )


@router.post("/restore/{history_id}", response_model=ModelConfigResponse)
def restore_from_history(
    history_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_superuser),
):
    history = db.query(ModelConfigHistory).filter(ModelConfigHistory.id == history_id).first()
    if not history:
        raise HTTPException(status_code=404, detail="历史记录不存在")

    existing = db.query(ModelConfig).filter(ModelConfig.id == history.config_id).first()

    if existing:
        existing.base_url = history.base_url
        existing.model_name = history.model_name
        existing.api_key = history.api_key
        existing.config_type = history.config_type
        db.commit()
        db.refresh(existing)
        _record_history(db, existing, "restored", user.username)
        db.commit()
        db.refresh(existing)
        return existing
    else:
        new_config = ModelConfig(
            name=f"{history.name} (已恢复)",
            base_url=history.base_url,
            model_name=history.model_name,
            api_key=history.api_key,
            config_type=history.config_type,
        )
        db.add(new_config)
        db.commit()
        db.refresh(new_config)
        _record_history(db, new_config, "restored", user.username)
        db.commit()
        db.refresh(new_config)
        return new_config


@router.post("/{config_id}/set-current", response_model=ModelConfigResponse)
def set_current_model(
    config_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_superuser),
):
    """将指定 LLM 配置设为当前使用。同一 config_type 只能有一个 current。"""
    config = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")

    # 将同类型的其他配置取消 current
    db.query(ModelConfig).filter(
        ModelConfig.config_type == config.config_type,
        ModelConfig.is_current == True,
    ).update({"is_current": False}, synchronize_session="fetch")

    config.is_current = True
    db.commit()
    db.refresh(config)

    return config
