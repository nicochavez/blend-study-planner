```markdown
# Study Planner — AI Engineer Challenge

Welcome! This is a take-home technical challenge. You'll be working on a real codebase — a study planning app — and solving user stories as you would on a normal day of work.

## The Project

AI Study Planner is a full-stack web application for organizing study goals, plans, and tasks. The backend is where the AI features live, and that is where most of your work will happen.

| Layer     | Technology                             |
| --------- | -------------------------------------- |
| Backend   | Python 3.12, FastAPI, SQLAlchemy 2, uv |
| Frontend  | React 18, TypeScript, Vite, Mantine 7  |
| Database  | PostgreSQL 16                          |
| Container | Docker Compose                         |

## Quick Start
```

docker compose up --build

```

On first boot, migrations run automatically and the database is seeded with sample data.

| Service   | URL                          |
|-----------|-------------------------------|
| Frontend  | http://localhost:5173        |
| API       | http://localhost:8000        |
| API Docs  | http://localhost:8000/docs   |

**Seed credentials:**

| Field    | Value    |
|----------|----------|
| Username | admin    |
| Password | admin123 |

If port 8000 is already in use, change `"8000:8000"` to `"8001:8000"` in `docker-compose.yml`.

## Your Task

You have received **3 user stories** alongside this document. Treat them exactly like a normal day of work — understand the codebase, and implement your solutions.

We expect you to attempt all three — give each one your best. If you run out of time on one, document in a markdown file your approach instead: the decisions you would have made, the trade-offs involved, and how you would have implemented it.

### Stack freedom

You are free to use any LLM provider and tools (LangChain, LlamaIndex, OpenAI, Anthropic, etc.). You may use any tools you consider appropriate, whether local or cloud-based, free or paid. There are no constraints on what you use, as long as the solution runs. If your implementation requires API keys or additional environment variables, document them clearly in your PR so we can run the solution ourselves.

## Submission

1. Use this repository as a template to create your own.
2. For each user story you solve, open a **Pull Request to main** within your repo following good engineering practices.
3. Send us the link to your repository when you're done.

## A Note on AI

The use of AI tools (GitHub Copilot, ChatGPT, Claude, Cursor, etc.) is **encouraged and allowed**. We use AI tools in our day-to-day work and expect engineers to leverage them effectively.

## User Stories

### 1. Task Generation with Structured Output + Validation

As a user, I want the system to automatically generate study tasks from my plan goal, so that I can quickly start working on it.

**Acceptance Criteria**

- Add endpoint: `POST /plans/{id}/generate-tasks`
- Use an LLM to generate tasks based on:
  - plan goal
  - hours per week
  - due date (if present)
- Output must be strictly structured (JSON) and mapped to a task
- Tasks must be persisted in DB

### 2. Study Plan Document Chat (RAG)

As a user, I want to upload documents to a study plan and ask questions about them, so that I can better understand my study materials.

**Acceptance Criteria**

- Users can upload documents associated with a study plan.
- Documents are processed and made searchable.
- Add an endpoint to ask questions about a plan's documents.
- The system returns answers based on the uploaded documents.
- Answers should be grounded in the available content and handle cases where no relevant information is found.
- Document data must be isolated per plan.

### 3. Planning Agent for Multi-step Plan Generation

As a user, I want the system to intelligently plan my study tasks considering multiple constraints, so that the plan is realistic and well-structured.

**Acceptance Criteria**

- Implement an agent-based approach for plan generation
- Agent should:
  - break down the goal into subtopics
  - generate tasks iteratively
  - validate constraints (hours, scope)
- Agent may use tools such as:
  - task generator
  - constraint validator
  - knowledge retrieval (RAG)
```
