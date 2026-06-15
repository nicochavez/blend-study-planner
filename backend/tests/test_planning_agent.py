"""Tests for US3 — the planning agent (multi-step plan generation).

Runs fully offline: a scripted fake tool-calling chat model, an in-memory
LangGraph checkpointer, and a temp FAISS directory. No network calls.
"""

import pytest
from app.api.deps import get_checkpointer
from app.core.config import settings
from app.main import app
from app.schemas.study_plan_agent import PlanTaskDraft
from app.schemas.study_task import GeneratedTask, GeneratedTaskList
from app.utils.ai import planning_tools
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver


class FakeToolCallingChatModel(FakeMessagesListChatModel):
    """A FakeMessagesListChatModel that accepts (and ignores) bind_tools."""

    def bind_tools(self, tools, **kwargs):
        return self


@pytest.fixture
def plan(client):
    user = client.post("/users", json={"name": "Alice"}).json()
    return client.post(
        "/plans",
        json={"user_id": user["id"], "goal": "Learn Python", "hours_per_week": 5.0},
    ).json()


@pytest.fixture(autouse=True)
def ai_env(monkeypatch):
    """In-memory checkpointer so tests don't need Postgres."""
    saver = InMemorySaver()
    app.dependency_overrides[get_checkpointer] = lambda: saver
    yield
    app.dependency_overrides.pop(get_checkpointer, None)


def _install_agent_model(monkeypatch, responses):
    fake = FakeToolCallingChatModel(responses=responses)
    monkeypatch.setattr(
        "app.services.planning_agent_service.get_chat_model", lambda: fake
    )
    return fake


def _submit_tool_call(subtopics, tasks, call_id="1"):
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "submit_plan",
                "args": {"subtopics": subtopics, "tasks": tasks},
                "id": call_id,
            }
        ],
    )


# ---------------------------------------------------------------------------
# validate_constraints / compute_budget_hours (pure functions)
# ---------------------------------------------------------------------------


def test_compute_budget_hours_with_target_date(plan, client):
    from datetime import date, timedelta

    from app.models.study_plan import StudyPlan

    p = StudyPlan(
        id=1,
        user_id=1,
        goal="x",
        hours_per_week=10.0,
        target_date=date.today() + timedelta(days=14),
    )
    # 14 days -> ceil(14/7) = 2 weeks
    assert planning_tools.compute_budget_hours(p) == 20.0


def test_compute_budget_hours_without_target_date():
    from app.models.study_plan import StudyPlan

    p = StudyPlan(id=1, user_id=1, goal="x", hours_per_week=10.0, target_date=None)
    assert (
        planning_tools.compute_budget_hours(p)
        == 10.0 * settings.DEFAULT_PLAN_WEEKS
    )


def test_validate_constraints_ok():
    tasks = [
        PlanTaskDraft(title="A", estimated_hours=4.0, subtopic="Basics"),
        PlanTaskDraft(title="B", estimated_hours=4.0, subtopic="Advanced"),
    ]
    result = planning_tools.validate_constraints(
        tasks, ["Basics", "Advanced"], budget_hours=10.0
    )
    assert result.ok is True
    assert result.total_hours == 8.0
    assert result.over_by == 0.0
    assert result.issues == []


def test_validate_constraints_over_budget():
    tasks = [PlanTaskDraft(title="A", estimated_hours=20.0, subtopic="Basics")]
    result = planning_tools.validate_constraints(
        tasks, ["Basics", "Advanced"], budget_hours=10.0
    )
    assert result.ok is False
    assert result.over_by > 0
    assert any("exceeds the budget" in issue for issue in result.issues)


def test_validate_constraints_empty_plan_and_bad_scope():
    result = planning_tools.validate_constraints([], [], budget_hours=10.0)
    assert result.ok is False
    assert "Plan has no tasks." in result.issues
    assert any("Expected 2-" in issue for issue in result.issues)


def test_validate_constraints_subtopic_without_tasks():
    tasks = [PlanTaskDraft(title="A", estimated_hours=2.0, subtopic="Basics")]
    result = planning_tools.validate_constraints(
        tasks, ["Basics", "Advanced"], budget_hours=10.0
    )
    assert result.ok is False
    assert any("Subtopics with no tasks" in issue for issue in result.issues)


# ---------------------------------------------------------------------------
# retrieve_knowledge / generate_tasks_for_subtopic tools
# ---------------------------------------------------------------------------


def test_retrieve_knowledge_no_documents(monkeypatch):
    monkeypatch.setattr(planning_tools, "similarity_search", lambda *a, **k: [])
    tools = planning_tools.build_planning_tools(1, "Learn Python", 10.0, {})
    retrieve = next(t for t in tools if t.name == "retrieve_knowledge")
    out = retrieve.invoke({"query": "anything"})
    assert "no relevant content" in out.lower()


def test_generate_tasks_for_subtopic(monkeypatch):
    monkeypatch.setattr(planning_tools, "similarity_search", lambda *a, **k: [])

    class _FakeStructuredModel:
        def invoke(self, _messages):
            return GeneratedTaskList(
                tasks=[GeneratedTask(title="Read docs", estimated_hours=2.0)]
            )

    class _FakeChatModel:
        def with_structured_output(self, _schema):
            return _FakeStructuredModel()

    monkeypatch.setattr(planning_tools, "get_chat_model", lambda: _FakeChatModel())

    tools = planning_tools.build_planning_tools(1, "Learn Python", 10.0, {})
    gen = next(t for t in tools if t.name == "generate_tasks_for_subtopic")
    out = gen.invoke({"subtopic": "Basics", "hours_budget": 5.0})
    assert out == [{"title": "Read docs", "estimated_hours": 2.0}]


# ---------------------------------------------------------------------------
# Agent / service / endpoint integration
# ---------------------------------------------------------------------------


def test_agent_plan_persists_tasks(client, plan, monkeypatch):
    monkeypatch.setattr(planning_tools, "similarity_search", lambda *a, **k: [])
    _install_agent_model(
        monkeypatch,
        responses=[
            _submit_tool_call(
                subtopics=["Basics", "Advanced"],
                tasks=[
                    {"title": "Learn syntax", "estimated_hours": 3.0, "subtopic": "Basics"},
                    {"title": "Build a project", "estimated_hours": 5.0, "subtopic": "Advanced"},
                ],
            ),
            AIMessage(content="Done."),
        ],
    )

    response = client.post(f"/plans/{plan['id']}/agent-plan")
    assert response.status_code == 201
    tasks = response.json()
    assert {t["title"] for t in tasks} == {"Learn syntax", "Build a project"}
    assert all(t["plan_id"] == plan["id"] for t in tasks)

    listed = client.get(f"/plans/{plan['id']}/tasks").json()
    assert len(listed) == 2


def test_agent_plan_plan_not_found(client, monkeypatch):
    monkeypatch.setattr(planning_tools, "similarity_search", lambda *a, **k: [])
    _install_agent_model(monkeypatch, responses=[AIMessage(content="n/a")])

    response = client.post("/plans/999/agent-plan")
    assert response.status_code == 404


def test_agent_plan_no_submission_is_502(client, plan, monkeypatch):
    monkeypatch.setattr(planning_tools, "similarity_search", lambda *a, **k: [])
    # The agent replies without ever calling submit_plan.
    _install_agent_model(monkeypatch, responses=[AIMessage(content="I'm done.")])

    response = client.post(f"/plans/{plan['id']}/agent-plan")
    assert response.status_code == 502


def test_agent_plan_invalid_submission_is_422(client, plan, monkeypatch):
    monkeypatch.setattr(planning_tools, "similarity_search", lambda *a, **k: [])
    # Way over budget (hours_per_week=5 -> default 8-week budget = 40h).
    _install_agent_model(
        monkeypatch,
        responses=[
            _submit_tool_call(
                subtopics=["Basics", "Advanced"],
                tasks=[
                    {"title": "Huge task", "estimated_hours": 100.0, "subtopic": "Basics"},
                    {"title": "Another", "estimated_hours": 100.0, "subtopic": "Advanced"},
                ],
            ),
            AIMessage(content="Done."),
        ],
    )

    response = client.post(f"/plans/{plan['id']}/agent-plan")
    assert response.status_code == 422


def test_agent_plan_llm_failure_is_502(client, plan, monkeypatch):
    monkeypatch.setattr(planning_tools, "similarity_search", lambda *a, **k: [])

    class _BoomModel(FakeToolCallingChatModel):
        def _generate(self, *args, **kwargs):
            raise RuntimeError("anthropic exploded")

    monkeypatch.setattr(
        "app.services.planning_agent_service.get_chat_model",
        lambda: _BoomModel(responses=[]),
    )

    response = client.post(f"/plans/{plan['id']}/agent-plan")
    assert response.status_code == 502
