# AI Study Planner

A study planning app to organize goals, plans, and tasks. JWT-based auth, progress tracking, target dates, and AI features (LLM task generation, document chat via RAG).

## Stack

| Layer      | Technology                                                          |
|------------|----------------------------------------------------------------------|
| Backend    | Python 3.12, FastAPI, SQLAlchemy 2, uv                              |
| Database   | PostgreSQL 16 (SQLite for tests)                                    |
| Migrations | Alembic                                                              |
| Frontend   | React 18, TypeScript, Vite, Mantine 7                               |
| AI         | LangChain + LangGraph, Anthropic Claude, FAISS (local vector stores), fastembed |
| Container  | Docker Compose                                                       |

## Anthropic API Key

The AI features (task generation and document chat) call the Anthropic API and require an API key.

1. Get a key from the [Anthropic Console](https://console.anthropic.com/).
2. Provide it via the `ANTHROPIC_API_KEY` environment variable, using whichever option matches how you're running the app:

   - **Docker Compose**: export it in your shell before starting the stack, or put it in a `.env` file in the project root (Compose loads this automatically):

     ```bash
     export ANTHROPIC_API_KEY=sk-ant-...
     docker compose up --build
     ```

     or in `./.env`:

     ```
     ANTHROPIC_API_KEY=sk-ant-...
     ```

   - **Backend without Docker**: put it in `backend/.env`:

     ```
     ANTHROPIC_API_KEY=sk-ant-...
     ```

If the key is missing or invalid, the AI endpoints (`/plans/{id}/generate-tasks`, `/plans/{id}/chat`) return a `502` error — the rest of the app works normally without it.

## Quick Start

```bash
docker compose up --build
```

On first boot the backend automatically runs migrations and seeds the database with sample data.

| Service   | URL                         |
|-----------|-----------------------------|
| Frontend  | http://localhost:5173       |
| API       | http://localhost:8000       |
| API Docs  | http://localhost:8000/docs  |

> If port 8000 is already in use, change `"8000:8000"` to `"8001:8000"` in `docker-compose.yml`.

## Seed Data

The seeder runs automatically on every `compose up` (idempotent — skips if the admin user already exists).

| Credential | Value      |
|------------|------------|
| Username   | `admin`    |
| Password   | `admin123` |

Four sample plans are created (AWS cert, TypeScript, Clean Code, System Design) with multiple tasks at various completion states so you can see the progress bars and date badges in action.

To re-seed from scratch, remove the database volume and restart:

```bash
docker compose down -v && docker compose up --build
```

## API Endpoints

| Method | Path                            | Description                          |
|--------|---------------------------------|---------------------------------------|
| POST   | /auth/register                  | Create account                        |
| POST   | /auth/login                     | Sign in, get JWT                      |
| GET    | /users/{id}/plans               | List user's plans                     |
| POST   | /plans                          | Create study plan                     |
| GET    | /plans/{id}                     | Get study plan                        |
| PATCH  | /plans/{id}                     | Update plan                           |
| POST   | /plans/{id}/tasks               | Add task to plan                      |
| GET    | /plans/{id}/tasks               | List tasks                            |
| POST   | /plans/{id}/generate-tasks      | AI-generate tasks for the plan        |
| PATCH  | /plans/{id}/tasks/{taskId}      | Toggle task completion                |
| POST   | /plans/{id}/documents           | Upload a document for RAG chat        |
| GET    | /plans/{id}/documents           | List uploaded documents               |
| POST   | /plans/{id}/chat                | Chat with an AI assistant about the plan |

## Development

### Backend tests

```bash
cd backend
uv sync --all-groups
uv run pytest tests/ -v
```

### Backend only (no Docker)

```bash
cd backend
uv sync --all-groups
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/study_planner \
  uv run uvicorn app.main:app --reload
```

### Frontend only (no Docker)

```bash
cd frontend
npm install
npm run dev
```

## Architecture

```
backend/app/
├── api/routers/   → HTTP layer (parse request, return response)
├── api/deps.py    → FastAPI dependency providers (wire Session → Service)
├── services/      → Business logic, raises HTTPExceptions (404, 502, etc.)
├── repositories/  → Database access only (no business logic)
├── models/        → SQLAlchemy ORM models
├── schemas/       → Pydantic request/response/structured-output models
├── core/          → Config (Settings/env vars), DB session, JWT/bcrypt helpers
├── utils/ai/      → LLM, embeddings, vector store, prompt singletons
└── seed.py        → Idempotent sample data seeder

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
