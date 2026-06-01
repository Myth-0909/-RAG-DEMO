# Project Guidelines

## Architecture
- Backend: FastAPI + SQLAlchemy + Alembic (Python)
- Frontend: React + Ant Design Pro + UmiJS (TypeScript)
- Vector DB: Milvus at http://172.16.0.44:19530, Database: ljl_test
- Embedding: Qwen3-Embedding-8B via OpenAI-compatible API at http://172.16.76.112:8001/v1

## Conventions
- Python code follows PEP 8, use type hints everywhere
- API routes prefixed with `/api/v1/`
- Use Pydantic v2 models for request/response schemas
- SQLAlchemy models use `Base` from `app.database`
- Frontend uses TypeScript strict mode
- API calls encapsulated in `src/services/`

## Development
- Backend: `uvicorn app.main:app --reload` from `backend/`
- Frontend: `npm run dev` from `frontend/`
- Database migrations: `alembic revision --autogenerate -m "msg"` then `alembic upgrade head`

## Key Decisions
- LangChain for document processing, chunking, and RAG chains
- No LangGraph (standard RAG pipeline, no complex agent orchestration)
- SQLite for metadata (switchable to PostgreSQL)
- JWT auth with role-based access control
- Multiple chunking strategies: fixed, recursive, parent-child, semantic
