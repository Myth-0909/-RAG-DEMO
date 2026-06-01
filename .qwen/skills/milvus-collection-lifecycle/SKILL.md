---
name: milvus-collection-lifecycle
description: Milvus collection 生命周期管理中的常见陷阱和最佳实践（load/insert/delete/search）
source: auto-skill
extracted_at: '2026-06-01T10:15:00.000Z'
---

# Milvus Collection 生命周期管理

## 核心原则

Milvus 的 Collection 在执行 **search** 和 **delete** 操作前必须 `load()` 到内存，否则会报 `collection not loaded` 错误（code=101）。

## 操作清单

| 操作 | 需要 load()？ | 需要 flush()？ |
|------|:---:|:---:|
| `insert` | ❌ | ✅（写入后） |
| `search` | ✅ | ❌ |
| `delete` | ✅ | ✅（删除后） |
| `drop` | ❌ | ❌ |
| `stats` | ❌ | ❌ |

## 常见错误：删除时报 collection not loaded

**现象**：
```
MilvusException: (code=101, message=collection not loaded[collection=xxx])
```

**原因**：Milvus 的 `delete()` 需要 collection 在内存中，但创建/插入后 collection 不一定保持加载状态。

**修复**：

```python
def delete_by_document(self, collection_name: str, document_id: int):
    if not utility.has_collection(collection_name):
        return
    collection = Collection(collection_name)
    collection.load()  # ← 关键：必须先 load
    collection.delete(f"document_id == {document_id}")
    collection.flush()
```

## Collection 创建模板（含索引）

```python
from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, utility

def create_collection(name: str, dim: int = 4096):
    if utility.has_collection(name):
        return Collection(name)

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(name="chunk_text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="parent_text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="metadata", dtype=DataType.JSON),
        FieldSchema(name="document_id", dtype=DataType.INT64),
        FieldSchema(name="chunk_index", dtype=DataType.INT64),
    ]
    schema = CollectionSchema(fields=fields)
    collection = Collection(name=name, schema=schema)

    # 创建向量索引
    index_params = {
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "params": {"nlist": 128},
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    return collection
```

## Embedding 维度验证

创建 collection 前务必验证 embedding 模型的实际输出维度：

```python
# 测试实际维度
response = client.embeddings.create(model=model_name, input=["test"])
actual_dim = len(response.data[0].embedding)
# Qwen3-Embedding-8B → 4096（不是文档中常见的 1024）
```

配置文件中 `EMBEDDING_DIM` 必须与实际维度一致，否则 insert 时会报维度不匹配错误。

### 维度不匹配时的自动重建

当 embedding 模型更换或配置错误时，已存在的 collection 可能维度不匹配。插入时会报：

```
MilvusException: (code=1100, message=the dim (4096) of field data(embedding) is not equal to schema dim (1024): invalid parameter[expected=1024][actual=4096])
```

**修复**：在 `create_collection` 中添加维度验证和自动重建逻辑：

```python
def create_collection(self, name: str, dim: int = None):
    dim = dim or settings.EMBEDDING_DIM
    if utility.has_collection(name):
        collection = Collection(name)
        # Verify dim matches, drop and recreate if not
        try:
            schema = collection.schema
            for field in schema.fields:
                if field.dtype == 101:  # FLOAT_VECTOR
                    existing_dim = field.params.get("dim", 0)
                    if existing_dim != dim:
                        self.drop_collection(name)
                        break
            else:
                return collection
        except Exception:
            pass
    
    # ... 继续创建 collection
```

这个模式确保：
1. 如果 collection 不存在，正常创建
2. 如果存在且维度匹配，直接返回
3. 如果存在但维度不匹配，删除并重建（会丢失数据，适用于开发环境）

## 批量插入模式

```python
def insert(self, collection_name, embeddings, chunk_texts, parent_texts,
           metadata_list, document_ids, chunk_indices):
    collection = Collection(collection_name)
    data = [
        embeddings,       # FLOAT_VECTOR
        chunk_texts,      # VARCHAR
        parent_texts,     # VARCHAR
        metadata_list,    # JSON
        document_ids,     # INT64
        chunk_indices,    # INT64
    ]
    result = collection.insert(data)
    collection.flush()
    return result.primary_keys
```

## 连接管理

```python
from pymilvus import connections

def _ensure_connected(self):
    try:
        connections.connect(
            alias="default",
            host=host,
            port=port,
            db_name=db_name,
        )
    except Exception:
        pass  # 已连接
```

## 安全删除 Collection

```python
def drop_collection(self, name: str):
    if utility.has_collection(name):
        utility.drop_collection(name)
```

注意：`drop` 不需要 `load()`，也不需要先 `delete` 数据。
