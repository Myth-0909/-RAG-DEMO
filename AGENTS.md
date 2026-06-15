# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Architecture

- Backend: FastAPI + SQLAlchemy + Alembic (Python), at `backend/`
- Frontend: React 18 + Vite + React Router 6 + Ant Design 5 (TypeScript), at `frontend/`
- Vector DB: Milvus (pymilvus) at `172.16.0.44:19530`, database `ljl_test`
- Embedding: Qwen3-Embedding-8B via OpenAI-compatible API
- LLM: dynamically configured via `model_configs` table, with `.env` fallback

## Development Commands

```bash
# Backend
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
alembic revision --autogenerate -m "msg"    # create migration
alembic upgrade head                        # apply migrations
alembic downgrade -1                        # rollback one migration

# Frontend
cd frontend
npm run dev          # Vite dev server on port 3000, proxies /api -> localhost:8000
npm run build        # tsc -b && vite build

# One-click start
./start.sh           # starts both backend (8000) and frontend (3000)
```

## Key Conventions

- API routes: `backend/app/api/v1/<module>.py`, all prefixed `/api/v1/`
- Pydantic v2 schemas in `app/schemas/`, SQLAlchemy models in `app/models/`
- Frontend API calls in `src/services/api.ts`, axios base `/api/v1`, token auto-attached via interceptor
- JWT auth — `get_current_user` dependency for auth, `get_current_superuser` for admin, `require_permission(code)` for fine-grained control
- Python: PEP 8 with type hints. TypeScript: strict mode.
- SQLite by default (switchable to PostgreSQL), file `rag_system.db`

## Backend Structure

### Models (`app/models/`, 13 models)
- **auth**: `User`, `Role`, `Permission`, `UserRole` (role_permissions association table)
- **knowledge**: `KnowledgeBase`, `Document`, `DocumentChunk`, `Domain`
- **conversation**: `Conversation`, `ChatMessage`, `ConversationSummary` (long-term memory via embedding similarity)
- **config**: `ModelConfig` (dynamic LLM/embedding, `is_current` switches), `ModelConfigHistory` (audit trail)
- **tasks**: `ProcessingTask` (tracks 7-step document processing with JSON `events`)

### API Routes (`app/api/v1/`, 8 modules)
| Module | Prefix | Key endpoints |
|--------|--------|---------------|
| `auth.py` | `/auth` | login, user CRUD (superuser) |
| `roles.py` | `/roles` | role CRUD, permission tree, permission CRUD (superuser) |
| `knowledge.py` | `/knowledge` | KB CRUD, doc upload/delete, chunk listing, SSE process stream |
| `chat.py` | `/chat` | RAG query (streaming + non-streaming), conversation auto-creation |
| `conversations.py` | `/conversations` | conversation CRUD, message listing |
| `domains.py` | `/domains` | domain CRUD with system prompts |
| `model_configs.py` | `/model-configs` | model config CRUD, history, restore, set-current |
| `processing_tasks.py` | `/processing-tasks` | task listing/filtering, retry |

### Services (`app/services/`, 11 files)
- **`milvus_service.py`** — `MilvusService` class: connect, create/drop collection, insert/search/delete vectors. IVF_FLAT index, COSINE metric.
- **`embedding.py`** — `embed_texts()`, `embed_query()`. Reads current embedding config from DB (fallback to `.env`).
- **`rag_chain.py`** — `rag_query()` + `rag_query_stream()` (SSE). Retrieves context from Milvus, formats prompt, calls LLM, returns answer+sources. Includes conversation memory and chat history (max 5 turns).
- **`document.py`** — Text extraction (PDF: pypdf+pdfplumber+OCR; DOCX: python-docx+OCR), `process_document_stream()` 7-step SSE pipeline (extract→clean→apply→analyze→chunk→embed→complete).
- **`chunking.py`** — 5 strategies: fixed, recursive, parent_child, semantic, hybrid. Keeps Markdown tables intact in parent_child and hybrid.
- **`content_analyzer.py`** — `ContentProfile` with hierarchy/structure/narrative/density scores. `clean_content()` for rule-based cleaning.
- **`llm_analyzer.py`** — LLM-driven cleaning assessment and chunking strategy analysis. 6000-char samples, retry up to 2x, rule-based fallbacks.
- **`memory_service.py`** — `ConversationSummary` embedding storage, cosine-similarity retrieval for long-term memory.
- **`model_config_service.py`** — `get_current_llm_config()`, `get_current_embedding_config()`. DB-first with `.env` fallback. Auto-normalizes base URLs.
- **`background_processor.py`** — Async wrapper that runs `process_document_stream` and persists events to `ProcessingTask`.

### Core (`app/core/`)
- **`security.py`** — bcrypt password hashing, JWT encode/decode with `HS256`
- **`deps.py`** — `get_current_user`, `get_current_superuser`, `require_permission(code)` factory

### Config (`app/config.py`)
`Settings` class (pydantic-settings) reads from `.env`. Key items: `DATABASE_URL`, `SECRET_KEY`, `MILVUS_HOST/PORT/DATABASE`, `EMBEDDING_BASE_URL/API_KEY/MODEL/DIM`, `LLM_BASE_URL/API_KEY/MODEL` (DB config takes priority when available).

## Frontend Structure

### Routes (all protected except `/login`)
- `/` → redirects to `/knowledge`
- `/knowledge`, `/chat`, `/domain`, `/model-config`, `/processing-tasks`
- `/system/users`, `/system/roles`

### Design System
- Primary color: `#e8653a`, layout background: `#f4f3f1`
- Font: DM Sans (Google Fonts)
- Custom Ant Design tokens in `App.tsx`, extensive overrides in `global.css`
- Sidebar: dark theme (`#1c1b19`), collapsible (220px/64px)

### Components (`src/components/`)
- `AnalysisDialog.tsx` — modal showing completed document analysis (content profile, scores, strategy decision)
- `ProcessAnalysisDialog.tsx` — drawer with real-time 7-step SSE processing display, LLM thinking tokens

### Auth
Token + user info in `localStorage` via `utils/auth.ts`. Axios interceptor attaches `Bearer` token. 401 responses clear token and redirect to `/login`.

## Document Processing Pipeline

7-step SSE pipeline (defined in `document.py:process_document_stream`):
1. **extract** — text/tables/images via pypdf/pdfplumber/docx/OCR
2. **clean** — LLM assesses cleaning needs (streams thinking tokens)
3. **apply** — rule-based `clean_content()` normalization
4. **analyze** — LLM analyzes content for optimal chunking strategy (streams thinking tokens)
5. **chunk** — execute chosen strategy (fixed/recursive/parent_child/semantic/hybrid)
6. **embed** — batch embed (size 50), insert to Milvus + DB
7. **complete** — update document status, save analysis report

Background processing via `background_processor.py`, progress persisted to `processing_tasks` table events JSON.

## Chat / RAG Flow

1. `chat.py` receives query → get/create conversation (auto-title from first 20 chars of question)
2. `memory_service.retrieve_relevant_memories()` — cosine similarity on summary embeddings
3. `rag_chain.rag_query()` — embed question → search Milvus across selected KBs → merge + rank results → build prompt with context + memory + chat history → call LLM → return answer + sources
4. Save user message + assistant response, update conversation summary
5. Streaming variant uses SSE, yielding `sources`, `token`, `done` events

## Dynamic Model Config

`ModelConfig` table stores LLM/embedding connections. `is_current` flag determines active config (one per type). Service functions (`get_current_llm_config()`, `get_current_embedding_config()`) check DB first, fall back to `.env`. All config changes are audited in `ModelConfigHistory`. The `/model-configs` page in frontend manages this.
