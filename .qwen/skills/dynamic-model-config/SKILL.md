---
name: dynamic-model-config
description: 数据库驱动的 LLM 模型配置管理——通过 DB 存储模型配置，支持运行时动态切换当前使用的 LLM，替代硬编码 .env 配置
source: auto-skill
extracted_at: '2026-06-04T03:07:20.029Z'
---

# 数据库驱动的动态模型配置

## 核心问题

RAG 系统的 LLM 配置（base_url / api_key / model_name）通常硬编码在 `.env` 文件中：
1. 切换模型必须修改 `.env` 并重启服务
2. 无法保留历史配置，回退困难
3. 无法在 UI 上直观管理多个模型配置
4. 每次修改配置没有审计记录

## 解决方案：DB 存储 + `is_current` 标记 + 运行时读取

### 数据模型

```python
class ModelConfig(Base):
    __tablename__ = "model_configs"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)  # 配置名称
    base_url = Column(String(500), nullable=False)
    model_name = Column(String(200), nullable=False)
    api_key = Column(String(500), nullable=False)
    config_type = Column(String(50), default="llm")  # llm / embedding
    is_active = Column(Boolean, default=True)
    is_current = Column(Boolean, default=False)  # 当前激活（每种 type 最多一个）
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ModelConfigHistory(Base):
    __tablename__ = "model_config_history"
    id = Column(Integer, primary_key=True)
    config_id = Column(Integer, nullable=False)
    action = Column(String(20), nullable=False)  # created/updated/deleted/restored
    name = Column(String(100))
    base_url = Column(String(500))
    model_name = Column(String(200))
    api_key = Column(String(500))
    config_type = Column(String(50))
    changed_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
```

### 关键 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/model-configs/` | 列出所有配置 |
| POST | `/model-configs/` | 新增配置 |
| PUT | `/model-configs/{id}` | 修改配置 |
| DELETE | `/model-configs/{id}` | 删除配置（保留历史） |
| POST | `/model-configs/{id}/set-current` | **设为当前使用** |
| GET | `/model-configs/{id}/history` | 查看单个配置的变更历史 |
| GET | `/model-configs/history/all` | 查看全部操作历史 |
| POST | `/model-configs/restore/{history_id}` | 从历史记录恢复配置 |

### 设为当前使用（核心逻辑）

同一 `config_type` 只能有一个 `is_current=True`：

```python
@router.post("/{config_id}/set-current")
def set_current_model(config_id: int, db: Session):
    config = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()

    # 取消同类型的其他 current
    db.query(ModelConfig).filter(
        ModelConfig.config_type == config.config_type,
        ModelConfig.is_current == True,
    ).update({"is_current": False}, synchronize_session="fetch")

    config.is_current = True
    db.commit()
```

### 运行时动态读取服务

**文件**: `backend/app/services/model_config_service.py`

```python
@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    model_name: str

def get_current_llm_config() -> LLMConfig:
    """从 DB 读取 is_current=True 的 LLM 配置，无则 fallback 到 .env"""
    try:
        db = _SessionLocal()
        try:
            config = db.query(ModelConfig).filter(
                ModelConfig.config_type == "llm",
                ModelConfig.is_current == True,
            ).first()
            if config:
                return LLMConfig(config.base_url, config.api_key, config.model_name)
        finally:
            db.close()
    except Exception:
        pass  # DB 不可用时 fallback

    return LLMConfig(settings.LLM_BASE_URL, settings.LLM_API_KEY, settings.LLM_MODEL)
```

### 服务层集成

**关键**：每次 LLM 调用时实时读取配置，不缓存 client 实例。

```python
# rag_chain.py
def get_llm_client():
    cfg = get_current_llm_config()
    return OpenAI(base_url=cfg.base_url, api_key=cfg.api_key)

def get_current_model_name() -> str:
    return get_current_llm_config().model_name

# 所有 LLM 调用替换为：
client = get_llm_client()
response = client.chat.completions.create(
    model=get_current_model_name(),  # 不再用 settings.LLM_MODEL
    ...
)
```

```python
# llm_analyzer.py — 同样每次创建新 client
def get_llm_client():
    cfg = get_current_llm_config()
    return OpenAI(base_url=cfg.base_url, api_key=cfg.api_key, timeout=_LLM_TIMEOUT)
```

### 变更记录

每次 CRUD 操作自动写入历史表：

```python
def _record_history(db, config, action, changed_by=None):
    history = ModelConfigHistory(
        config_id=config.id,
        action=action,  # created / updated / deleted / restored
        name=config.name,
        base_url=config.base_url,
        model_name=config.model_name,
        api_key=config.api_key,
        config_type=config.config_type,
        changed_by=changed_by,
    )
    db.add(history)
```

### 前端管理页面

**文件**: `frontend/src/pages/model-config/index.tsx`

功能：
- 表格展示所有配置（名称、类型、模型、URL、脱敏 API Key、状态）
- 新增/编辑 Modal（表单含 name/config_type/base_url/model_name/api_key）
- **切换按钮**：非 current 的配置显示绿色「切换」按钮，点击调用 `set-current`
- 当前使用的配置显示 `✓ 当前使用` Tag
- 操作历史 Drawer：Timeline 展示变更历史，每条记录可「恢复此版本」
- API Key 脱敏显示：前 4 位 + `****` + 后 4 位

### 菜单和权限

1. 侧栏菜单新增入口（`AdminLayout.tsx`）
2. `seed_data.py` 添加 `model_config` 权限码
3. 已有数据库需手动执行权限补充脚本

### 切换流程

```
用户在 UI 点击「切换」
  → POST /model-configs/{id}/set-current
  → DB: 同类型其他 is_current=false, 目标 is_current=true
  → 下次 LLM 调用时 get_current_llm_config() 读到新配置
  → 自动使用新模型，无需重启
```

## 适用场景

- ✅ 需要频繁切换不同 LLM 模型（测试/对比）
- ✅ 需要保留配置历史便于回退
- ✅ 需要在 UI 上管理模型配置
- ✅ 多环境部署但模型地址不同

## 不适用场景

- ❌ 单模型固定部署，不需要切换
- ❌ 对安全性要求极高（API Key 明文存 DB）

## 关键注意事项

1. **不缓存 OpenAI client**：每次调用创建新实例，确保配置变更立即生效
2. **Fallback 到 .env**：DB 中没有 `is_current=True` 时自动使用 `.env` 配置
3. **每种 type 只能一个 current**：`set-current` 自动取消同类型的其他 current
4. **Embedding 不受影响**：当前实现只切换 LLM，Embedding 模型保持 `.env` 硬编码
5. **历史记录保留 API Key**：恢复时可以直接用历史版本的配置，无需重新输入 Key
