---
name: rag-model-testing
description: RAG 项目中 Embedding 和 LLM 模型的可用性测试、维度验证和配置最佳实践
source: auto-skill
extracted_at: '2026-06-01T10:30:00.000Z'
---

# RAG 模型配置与测试

## 核心原则

RAG 系统需要两类模型，必须分开配置和测试：

1. **Embedding 模型**：文本向量化（用于检索）
2. **LLM 对话模型**：生成回答（用于问答）

## 常见错误：用 Embedding 模型做对话

**现象**：配置文件中 LLM 和 Embedding 使用同一个模型名（如 `Qwen3-Embedding-8B`）

**问题**：Embedding 模型只支持 `/embeddings` 接口，调用 `/chat/completions` 会返回错误。

**修复**：确保配置两个不同的模型：

```env
# Embedding 模型（向量化）
EMBEDDING_BASE_URL=http://172.16.76.112:8001/v1
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B

# LLM 对话模型（问答生成）
LLM_BASE_URL=http://172.16.76.112:8000/v1
LLM_MODEL=google/gemma-4-31B-it
```

## 模型可用性测试流程

### 1. 检查服务是否运行

```bash
# 检查 Embedding 服务
curl -s http://172.16.76.112:8001/v1/models \
  -H "Authorization: Bearer $EMBEDDING_API_KEY" | jq '.data[].id'

# 检查 LLM 服务
curl -s http://172.16.76.112:8000/v1/models \
  -H "Authorization: Bearer $LLM_API_KEY" | jq '.data[].id'
```

**预期输出**：模型 ID 列表，确认模型已加载。

### 2. 测试 Embedding 模型

```python
from openai import OpenAI

client = OpenAI(
    base_url='http://172.16.76.112:8001/v1',
    api_key='sk-xxx'
)

response = client.embeddings.create(
    model='Qwen/Qwen3-Embedding-8B',
    input=['测试文本']
)

embedding = response.data[0].embedding
print(f'向量维度: {len(embedding)}')  # 关键：记录实际维度
```

**成功标志**：返回向量数组，无异常。

### 3. 测试 LLM 对话模型

```python
from openai import OpenAI

client = OpenAI(
    base_url='http://172.16.76.112:8000/v1',
    api_key='sk-xxx',
    timeout=60.0  # 首次推理可能较慢
)

response = client.chat.completions.create(
    model='google/gemma-4-31B-it',
    messages=[{'role': 'user', 'content': '用一句话介绍RAG'}],
    temperature=0.7,
    max_tokens=100
)

print(response.choices[0].message.content)
```

**成功标志**：返回自然语言回答，无异常。

## Embedding 维度验证

**关键步骤**：测试后必须验证实际维度并更新配置。

```python
actual_dim = len(response.data[0].embedding)
# Qwen3-Embedding-8B → 4096（不是常见的 1024）
```

然后在 `.env` 中更新：

```env
EMBEDDING_DIM=4096  # 必须与实际维度一致
```

**后果**：如果 `EMBEDDING_DIM` 与实际维度不匹配，Milvus insert 时会报维度错误。

## 常见错误与排查

### 502 Bad Gateway

**原因**：
- vLLM 服务未启动或已崩溃
- 模型加载失败（OOM、权重损坏）
- 反向代理连接后端失败

**排查**：
```bash
# 检查服务进程
ps aux | grep vllm

# 检查端口监听
netstat -tlnp | grep 8000

# 查看 vLLM 日志
docker logs vllm-container
```

### Connection Refused

**原因**：服务未启动或端口错误。

**排查**：
```bash
curl -v http://172.16.76.112:8000/v1/models
```

### Timeout

**原因**：首次推理需要加载模型到 GPU，可能耗时 30-60 秒。

**修复**：增加 timeout 参数：

```python
client = OpenAI(..., timeout=120.0)
```

## 配置模板

### .env 文件

```env
# Embedding 模型（向量化）
EMBEDDING_BASE_URL=http://172.16.76.112:8001/v1
EMBEDDING_API_KEY=sk-4f8a7b2c9d1e6f3a5b8c2d7e9f4a6b3c
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B
EMBEDDING_DIM=4096  # 通过测试验证的实际维度

# LLM 对话模型（问答生成）
LLM_BASE_URL=http://172.16.76.112:8000/v1
LLM_API_KEY=sk-7d2a5b1c9e4f8a0b3c6d9e1f2a5b8c4d
LLM_MODEL=google/gemma-4-31B-it
```

### Python 客户端初始化

```python
from openai import OpenAI

# Embedding 客户端
embedding_client = OpenAI(
    base_url=settings.EMBEDDING_BASE_URL,
    api_key=settings.EMBEDDING_API_KEY,
)

# LLM 客户端
llm_client = OpenAI(
    base_url=settings.LLM_BASE_URL,
    api_key=settings.LLM_API_KEY,
    timeout=60.0,  # 首次推理预留时间
)
```

## 测试脚本模板

```bash
#!/bin/bash
echo "=== 测试 Embedding 模型 ==="
python -c "
from openai import OpenAI
client = OpenAI(base_url='$EMBEDDING_BASE_URL', api_key='$EMBEDDING_API_KEY')
resp = client.embeddings.create(model='$EMBEDDING_MODEL', input=['test'])
print(f'✓ 维度: {len(resp.data[0].embedding)}')
"

echo "=== 测试 LLM 模型 ==="
python -c "
from openai import OpenAI
client = OpenAI(base_url='$LLM_BASE_URL', api_key='$LLM_API_KEY', timeout=60)
resp = client.chat.completions.create(
    model='$LLM_MODEL',
    messages=[{'role': 'user', 'content': 'hello'}],
    max_tokens=10
)
print(f'✓ 回答: {resp.choices[0].message.content}')
"
```

## 最佳实践清单

- [ ] Embedding 和 LLM 使用不同的模型和服务端口
- [ ] 启动前测试两个模型的可用性
- [ ] 验证 Embedding 实际维度并更新配置
- [ ] LLM 客户端设置合理的 timeout（60-120秒）
- [ ] 生产环境监控模型服务健康状态
- [ ] 准备模型服务的重启和故障恢复方案
