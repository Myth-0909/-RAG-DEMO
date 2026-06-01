# RAG 知识库管理系统

基于 FastAPI + React + Milvus 的企业级 RAG 知识库管理平台。

## 技术栈

- **后端**: Python FastAPI / SQLAlchemy / Alembic / LangChain
- **前端**: React 18 / Ant Design Pro / UmiJS
- **向量库**: Milvus
- **Embedding**: Qwen3-Embedding-8B (OpenAI 兼容 API)
- **认证**: JWT

## 功能模块

- 权限管理（用户、角色、菜单、操作）
- 知识库管理（文件上传、多策略分块）
- 智能问答（RAG 检索增强生成、流式输出）
- 专业知识管理（领域切换、Prompt 配置）

## 快速开始

### 后端

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 修改 .env 中的配置
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

## 项目结构

```
test_rag/
├── backend/          # FastAPI 后端
├── frontend/         # React + Ant Design Pro 前端
└── README.md
```
