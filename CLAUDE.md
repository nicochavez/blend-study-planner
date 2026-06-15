# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

AI Study Planner: a full-stack app (FastAPI + React/Mantine) for organizing study goals, plans, and tasks, with AI features (LLM task generation, RAG document chat, planning agent — see `userStories.md` for the three user stories being implemented).

| Layer      | Technology                             |
|------------|-----------------------------------------|
| Backend    | Python 3.12, FastAPI, SQLAlchemy 2, uv  |
| Database   | PostgreSQL 16 (SQLite for tests)        |
| Migrations | Alembic                                 |
| Frontend   | React 18, TypeScript, Vite, Mantine 7   |
| AI         | LangChain + LangGraph, Anthropic Claude, FAISS (local, per-plan vector stores), fastembed (local embeddings) |
| Container  | Docker Compose                          |

## Commands

### Run everything
```bash
docker compose up --build
```
Frontend: http://localhost:5173, API: http://localhost:8000, Docs: http://localhost:8000/docs. Migrations + seed run automatically on boot (idempotent — admin/admin123).

### Backend (no Docker)
```bash
cd backend
uv sync --all-groups
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/study_planner uv run uvicorn app.main:app --reload
```

### Backend tests
```bash
cd backend
uv run pytest tests/ -v
uv run pytest tests/test_plans.py::test_name -v   # single test
```
Tests use SQLite (`test.db`) with tables created/dropped per-test (see `tests/conftest.py`). No real Postgres needed for tests.

### Migrations
```bash
cd backend
uv run alembic revision -m "description"   # create new migration
uv run alembic upgrade head                  # apply
```

### Frontend (no Docker)
```bash
cd frontend
npm install
npm run dev        # vite dev server
npm run build       # tsc + vite build
```

## Architecture

```
backend/app/
├── api/routers/   → HTTP layer (parse request, return response)
├── api/deps.py    → FastAPI dependency providers (wire Session → Service)
├── services/      → Business logic, raises HTTPExceptions (404, 502, etc.)
├── repositories/  → Database access only (no business logic)
├── models/        → SQLAlchemy ORM models
├── schemas/        → Pydantic request/response/structured-output models
├── core/          → Config (Settings/env vars), DB session, JWT/bcrypt helpers
├── utils/ai/      → LLM, embeddings, vector store, prompt singletons
└── seed.py        → Idempotent sample data seeder (runs on every compose up)

frontend/src/
├── api/           → API client and token helpers
├── components/
│   ├── layout/    → AppHeader
│   ├── routing/   → PrivateRoute
│   ├── plan/      → PlanCard, CreatePlanModal
│   └── task/      → TaskItem, AddTaskModal
└── pages/
    ├── auth/      → LoginPage
    ├── dashboard/ → Dashboard
    └── plans/     → PlanDetail
```

Standard request flow: **router → service → repository → model**. Each layer should only talk to the layer directly below it. Add new endpoints by following this pattern: schema for I/O, repository method for DB access, service method for orchestration/validation/error handling, router method that's a thin pass-through, and wire it up in `api/deps.py`.

### AI utilities (`backend/app/utils/ai/`)

- `llm.py` — `get_chat_model()` returns a cached `ChatAnthropic` instance configured from `Settings` (model, temperature, API key). Use `.with_structured_output(SomePydanticModel)` for structured generation (see `task_generation_service.py` for the pattern: build messages from a `ChatPromptTemplate`, invoke, catch exceptions and raise `HTTPException(502, ...)`).
- `embeddings.py` — `get_embeddings()` returns a cached local `FastEmbedEmbeddings` model (no API key required).
- `vector_store.py` — per-plan FAISS indexes on disk under `FAISS_INDEX_DIR/plan_{id}/`. Directory-per-plan isolation guarantees one plan's documents are never retrieved for another plan. Use `add_documents(plan_id, docs)` and `similarity_search(plan_id, query, k=4)`.
- `prompts.py` — `ChatPromptTemplate` definitions for AI features, kept separate from service logic.

### Configuration

All config lives in `backend/app/core/config.py` (`Settings`, loaded from env / `.env`). Key AI-related settings: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `LLM_TEMPERATURE`, `EMBEDDING_MODEL`, `FAISS_INDEX_DIR`. `ANTHROPIC_API_KEY` is passed through from the host environment in `docker-compose.yml`.

### Auth

JWT-based (PyJWT + bcrypt), handled in `core/security.py` and `services/auth_service.py`. No roles — single user model.
