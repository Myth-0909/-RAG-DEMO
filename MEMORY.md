# Project Memory

## 固定规则

- **编码前必须先使用 /karpathy-guidelines skill**：遵循 Think Before Coding、Simplicity First、Surgical Changes、Goal-Driven Execution 原则

## 技术栈

- 后端：FastAPI + SQLAlchemy + LangChain
- 前端：React + Vite + Ant Design
- 向量库：Milvus（172.16.0.44:19530）
- 数据库：SQLite（本地开发）

## 项目结构

- 后端入口：`backend/app/main.py`
- 前端入口：`frontend/src/main.tsx`
- 模型配置：`backend/.env`（EMBEDDING + LLM）
- 知识库管理：`backend/app/api/v1/knowledge.py`
- 智能问答：`backend/app/api/v1/chat.py`

## 开发环境

- Python 3.11 + venv
- Node.js 18 + npm
- 后端端口：8000
- 前端端口：3000
