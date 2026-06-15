# User Story 3 — Planning Agent for Multi-step Plan Generation

> **Status:** Implementation plan
> **Branch target:** `user_story_3_planning_agent` → PR to `main`

## 1. The story

> As a user, I want the system to intelligently plan my study tasks considering
> multiple constraints, so that the plan is realistic and well-structured.

**Acceptance criteria**

- [ ] Implement an **agent-based** approach for plan generation.
- [ ] Agent must:
  - break down the goal into subtopics,
  - generate tasks iteratively,
  - validate constraints (hours, scope).
- [ ] Agent may use **tools**: task generator, constraint validator, knowledge retrieval (RAG).

## 2. Approach in one paragraph

We build a **LangChain Deep Agent** (`deepagents.create_deep_agent`) that owns a
multi-step planning loop: decompose goal → retrieve relevant context from the
plan's uploaded documents (reusing Story 2's RAG index) → draft tasks per
subtopic (reusing Story 1's structured task generator) → validate against the
hours/scope budget → revise until constraints pass → submit the final plan. The
service layer then persists the validated tasks transactionally. The Deep Agent
gives us, for free, the things that make "multi-step" robust: a built-in
**planning/todo middleware**, a **filesystem scratchpad** for intermediate work
(subtopic breakdown, draft task lists, validation notes), and a clean **tool**
abstraction. We follow the existing `router → service → repository → model`
layering and the AI-utils singleton conventions already in `app/utils/ai/`.

## 3. Why a Deep Agent (vs. a hand-rolled LangGraph like Story 2)

Story 2's `rag_graph.py` is a fixed two-node graph (retrieve → generate). Story 3
is genuinely iterative and open-ended (loop over subtopics, re-plan when
constraints fail), which is exactly what Deep Agents are built for:

- **Planning middleware** — the agent maintains an explicit todo list, so the
  "break down → generate → validate → revise" loop is driven by the model
  instead of hardcoded edges.
- **Filesystem scratchpad** — `write_file`/`read_file`/`edit_file`/`ls`/`grep`
  let the agent persist its subtopic breakdown and draft tasks across steps
  without bloating the message history. This is where the **deep-agents-memory**
  skill applies (backend selection below).
- **Tool use** — our three required tools (task generator, constraint validator,
  RAG retrieval) plug in directly.

## 4. Memory / backend strategy (deep-agents-memory skill)

The agent needs two distinct kinds of state. We map them to backends explicitly:

| State | Lifetime | Backend | Path |
|-------|----------|---------|------|
| Working scratchpad (subtopic breakdown, draft tasks, validation notes) | One planning run | `StateBackend` (default, thread-scoped) | `/scratch/...` |
| Conversation/run history (so a run is resumable, observable) | Per `thread_id` | LangGraph **checkpointer** (existing `PostgresSaver`) | n/a |
| Reusable planning notes (optional, e.g. "user prefers short tasks") | Across runs/sessions | `StoreBackend` route via `CompositeBackend` | `/memories/...` |

**Decision: ship with `CompositeBackend`** routing `/memories/` to a
`StoreBackend`, everything else to `StateBackend`:

```python
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

backend = lambda rt: CompositeBackend(
    default=StateBackend(rt),
    routes={"/memories/": StoreBackend(rt)},
)
agent = create_deep_agent(tools=..., backend=backend, store=store,
                          checkpointer=get_checkpointer())
```

Rationale and guardrails straight from the skill:

- **Never `FilesystemBackend` in a web server** — it gives the model real disk
  access. We are an API, so working files go to `StateBackend` (ephemeral,
  thread-isolated) and persistent files to `StoreBackend`.
- **`StoreBackend` requires a `store`** instance — pass one explicitly.
- **Production store must survive restarts** — use `PostgresStore`
  (`langgraph.store.postgres`) against the same `DATABASE_URL` the
  `PostgresSaver` checkpointer already uses; tests inject `InMemoryStore`. This
  mirrors the existing `checkpointer.py` lazy-singleton pattern exactly.
- **Thread isolation = plan isolation.** Use `thread_id = f"plan_{plan_id}:gen:{run_id}"`
  so one plan's scratchpad never leaks into another's, consistent with how Story
  2 scopes chat threads and how the FAISS dir-per-plan isolates documents.

> For a minimal first PR we could start with the plain default `StateBackend`
> (no store wiring) and add the `/memories/` route later. The plan below wires
> `CompositeBackend` from the start because the marginal cost is one
> lazy-singleton (`store.py`) and it satisfies "long-term memory" cleanly.

## 5. Tools the agent gets

All three are thin wrappers over **existing** code, defined as LangChain `@tool`
functions in a new `app/utils/ai/planning_tools.py`. `plan_id` and the
`Session`/budget are bound per-request (via `ToolRuntime`/closure) so the model
never has to supply them.

1. **`retrieve_knowledge(query: str) -> str`** — RAG retrieval.
   Wraps `vector_store.similarity_search(plan_id, query, k=settings.RAG_TOP_K)`.
   Returns concatenated chunk text (or a clear "no relevant documents" string so
   the agent can proceed goal-only). Reuses Story 2 infra unchanged; isolation is
   guaranteed by the per-plan FAISS directory.

2. **`generate_tasks_for_subtopic(subtopic: str, hours_budget: float) -> list[dict]`**
   — task generator. Reuses Story 1's structured-output call:
   `get_chat_model().with_structured_output(GeneratedTaskList)` against a new
   subtopic-scoped prompt. Returns candidate `{title, estimated_hours}` dicts.
   This keeps task generation strictly structured/validated (Pydantic), as in
   Story 1.

3. **`validate_constraints(tasks: list[dict]) -> dict`** — constraint validator.
   Pure function (no LLM): computes total estimated hours and checks against the
   **budget** derived from `hours_per_week` and `target_date`. Returns
   `{ ok: bool, total_hours, budget_hours, over_by, issues: [...] }` so the agent
   can read the feedback and revise. See §7 for the budget math.

A fourth tool, **`submit_plan(subtopics, tasks)`**, is the agent's "done" signal:
it records the final structured plan into agent state. The **service** (not the
agent) does the DB write afterward, keeping persistence transactional and outside
the model's control. (Alternative: read the final plan the agent wrote to
`/scratch/final_plan.json` via the backend — `submit_plan` is preferred for a
typed hand-off.)

## 6. Control flow

```
POST /plans/{id}/agent-plan
   │
   ▼
PlanningAgentService.generate_plan(plan_id)
   │  load plan (404 if missing); compute budget_hours
   ▼
deep_agent.invoke({messages:[system+goal]}, {thread_id, store})
   │
   │  agent loop (model-driven, via planning middleware + scratchpad):
   │    1. break goal into subtopics → write /scratch/subtopics.md
   │    2. for each subtopic: retrieve_knowledge → generate_tasks_for_subtopic
   │       → append to /scratch/draft_tasks.json
   │    3. validate_constraints(all tasks)
   │         ├─ ok=false → trim/rescope/re-estimate, goto 2/3
   │         └─ ok=true  → submit_plan(subtopics, tasks)
   ▼
service validates the submitted plan again (defense in depth),
persists via TaskRepository.create(...) in one unit of work
   ▼
return list[StudyTaskRead]  (201)
```

## 7. Constraint logic (the "realistic" part)

- **Budget hours**: if `target_date` is set,
  `weeks = max(1, ceil((target_date - today) / 7days))` and
  `budget_hours = hours_per_week * weeks`. If no `target_date`, treat
  `hours_per_week` as a soft weekly cap and target a sensible default horizon
  (e.g. `budget_hours = hours_per_week * settings.DEFAULT_PLAN_WEEKS`, default 8)
  — documented so reviewers can tune it.
- **Hours constraint**: `sum(estimated_hours) <= budget_hours * (1 + tolerance)`
  (tolerance e.g. 0.1). Each task `estimated_hours` stays within the Story 1
  bounds (`gt=0, le=100`).
- **Scope constraint**: every subtopic has ≥1 task; no empty plan; subtopic count
  within a reasonable range (e.g. 2–12) to avoid degenerate single-bucket or
  fragmented plans.
- Validation runs **inside the agent** (so it can react) *and once more in the
  service* before persisting.

## 8. Files to add / change

**New**

| File | Purpose |
|------|---------|
| `app/utils/ai/store.py` | Lazy `get_store()` singleton — `PostgresStore` in prod, mirrors `checkpointer.py`. |
| `app/utils/ai/planning_tools.py` | The `@tool` functions (RAG, task-gen, validate, submit) + per-request binding. |
| `app/utils/ai/planning_agent.py` | `build_planning_agent(...)`: `create_deep_agent` with tools, `CompositeBackend`, store, checkpointer, system prompt. |
| `app/services/planning_agent_service.py` | Orchestration: load plan, compute budget, invoke agent, re-validate, persist tasks. |
| `app/schemas/study_plan_agent.py` | `AgentPlanRequest` (optional knobs) / `AgentPlanResponse` (tasks + subtopics + budget summary). |
| `tests/test_planning_agent.py` | Unit/integration tests (agent + tools mocked). |

**Changed**

| File | Change |
|------|--------|
| `app/utils/ai/prompts.py` | Add `PLANNING_AGENT_SYSTEM_PROMPT` + a subtopic task-gen prompt. |
| `app/api/routers/plans.py` | Add `POST /plans/{id}/agent-plan`. |
| `app/api/deps.py` | Add `get_planning_agent_service` (wires `Session` + checkpointer + store). |
| `app/core/config.py` | Add `DEFAULT_PLAN_WEEKS`, `PLAN_HOURS_TOLERANCE`, `AGENT_MAX_SUBTOPICS` (and reuse `RAG_TOP_K`). |
| `pyproject.toml` / `uv.lock` | Add `deepagents` dependency; `uv add deepagents` (+ `langgraph-store` if separate). |

No new DB table or migration is required: tasks persist into the existing
`study_tasks` table via `TaskRepository.create`. (Optional future: a
`plan_generation_runs` audit table — out of scope for this PR.)

## 9. Endpoint

```
POST /plans/{plan_id}/agent-plan
  → 201 [StudyTaskRead]            # persisted, agent-validated tasks
  → 404 plan not found
  → 502 agent/LLM failure (wrapped, like Story 1/2)
  → 422 agent could not satisfy constraints after retries (optional)
```

Mirror Story 1's `generate-tasks` shape so the frontend reuses the same task
rendering. Replace-vs-append semantics (default: append; allow `?replace=true`)
to be decided in the PR — recommend **append** to match `generate-tasks`.

## 10. Error handling, safety, isolation

- Wrap `agent.invoke` and surface failures as `HTTPException(502, ...)`, matching
  `task_generation_service` and `chat_service`.
- Cap agent iterations (`recursion_limit` / max tool calls) so a confused agent
  can't loop forever or burn tokens; on exhaustion return the best validated
  draft or 422.
- DB writes happen only in the service, in one unit of work — the model cannot
  directly mutate the database (no DB tool exposed).
- Per-plan isolation preserved end to end: RAG dir-per-plan, agent `thread_id`
  namespaced by plan, store namespace keyed by plan/user.

## 11. Testing

Tests use SQLite + per-test create/drop (see `tests/conftest.py`) and must not
hit the network:

- **Tool unit tests** — `validate_constraints` math (under/over/edge budgets);
  `retrieve_knowledge` returns "no documents" gracefully; `generate_tasks_for_subtopic`
  with `get_chat_model` monkeypatched to a fake structured response.
- **Agent integration** — monkeypatch `get_chat_model` (and `get_store`/
  `get_checkpointer` → in-memory) with a scripted model that calls tools then
  `submit_plan`; assert tasks are persisted and constraint-valid.
- **Endpoint** — `POST /plans/{id}/agent-plan` 404 for missing plan, 201 +
  persisted tasks on success, 502 on agent failure.
- Reuse the existing override pattern: tests swap `get_checkpointer` for
  `InMemorySaver` and `get_store` for `InMemoryStore`.

## 12. Config / env to document in the PR

- `DEFAULT_PLAN_WEEKS` (default `8`) — horizon when no `target_date`.
- `PLAN_HOURS_TOLERANCE` (default `0.1`).
- `AGENT_MAX_SUBTOPICS` (default `12`), agent `recursion_limit`.
- Reuses existing `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `LLM_TEMPERATURE`,
  `RAG_TOP_K`, `RAG_SCORE_THRESHOLD`, `FAISS_INDEX_DIR`, `DATABASE_URL`.
- New dep: `deepagents` (note in PR description).

## 13. Implementation checklist

1. `uv add deepagents`; verify import + pin in `uv.lock`.
2. `app/utils/ai/store.py` — `get_store()` lazy `PostgresStore` singleton.
3. Prompts — system prompt (role, loop instructions, tool guidance, constraints)
   + subtopic task-gen prompt.
4. `planning_tools.py` — four tools, per-request binding of `plan_id`/budget/db.
5. `planning_agent.py` — `build_planning_agent(...)` with `CompositeBackend`.
6. `planning_agent_service.py` — orchestrate, re-validate, persist.
7. Schemas + router endpoint + `deps.py` wiring.
8. Config settings.
9. Tests (tools, agent, endpoint).
10. Update `CLAUDE.md` AI-utils section + PR notes (new dep/env, endpoint).

## 14. Trade-offs & alternatives considered

- **Deep Agent vs. plain LangGraph loop.** A hand-built `StateGraph` would work
  but we'd reimplement planning/todo tracking and a scratchpad. Deep Agents give
  those out of the box and read as "an agent," which is what the story asks for.
- **Persist inside the agent (DB tool) vs. in the service.** Service-side
  persistence keeps writes transactional and the model out of the database —
  chosen for safety. `submit_plan` is the typed hand-off boundary.
- **`StateBackend` only vs. `CompositeBackend` + store.** Starting with
  `CompositeBackend` costs one extra singleton and delivers genuine cross-run
  long-term memory; falls back gracefully to in-memory store in tests.
- **One-shot structured output vs. iterative agent.** Story 1 already does
  one-shot; Story 3's value is the iterative, constraint-aware loop, so we lean
  into multi-step tool use rather than a single big prompt.
```
