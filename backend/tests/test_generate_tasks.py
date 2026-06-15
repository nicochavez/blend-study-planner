import pytest
from app.schemas.study_task import GeneratedTask, GeneratedTaskList
from app.services import task_generation_service


@pytest.fixture
def plan(client):
    user = client.post("/users", json={"name": "Alice"}).json()
    return client.post(
        "/plans",
        json={"user_id": user["id"], "goal": "Learn Python", "hours_per_week": 10.0},
    ).json()


class _FakeStructuredModel:
    """Stands in for model.with_structured_output(GeneratedTaskList)."""

    def __init__(self, result):
        self._result = result

    def invoke(self, _messages):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class _FakeChatModel:
    def __init__(self, result):
        self._result = result

    def with_structured_output(self, _schema):
        return _FakeStructuredModel(self._result)


@pytest.fixture
def mock_llm(monkeypatch):
    """Patch the chat model used by the task generation service."""

    def _install(result):
        monkeypatch.setattr(
            task_generation_service,
            "get_chat_model",
            lambda: _FakeChatModel(result),
        )

    return _install


def test_generate_tasks_persists(client, plan, mock_llm):
    mock_llm(
        GeneratedTaskList(
            tasks=[
                GeneratedTask(title="Learn variables", estimated_hours=2.0),
                GeneratedTask(title="Learn functions", estimated_hours=3.0),
            ]
        )
    )

    response = client.post(f"/plans/{plan['id']}/generate-tasks")
    assert response.status_code == 201
    tasks = response.json()
    assert {t["title"] for t in tasks} == {"Learn variables", "Learn functions"}
    assert all(t["plan_id"] == plan["id"] for t in tasks)
    assert all(t["completed"] is False for t in tasks)

    # Persisted: visible via the normal listing endpoint.
    listed = client.get(f"/plans/{plan['id']}/tasks").json()
    assert len(listed) == 2


def test_generate_tasks_plan_not_found(client, mock_llm):
    mock_llm(GeneratedTaskList(tasks=[GeneratedTask(title="x", estimated_hours=1.0)]))
    response = client.post("/plans/999/generate-tasks")
    assert response.status_code == 404


def test_generate_tasks_empty_result_is_502(client, plan, mock_llm):
    mock_llm(GeneratedTaskList(tasks=[]))
    response = client.post(f"/plans/{plan['id']}/generate-tasks")
    assert response.status_code == 502


def test_generate_tasks_llm_failure_is_502(client, plan, mock_llm):
    mock_llm(RuntimeError("anthropic exploded"))
    response = client.post(f"/plans/{plan['id']}/generate-tasks")
    assert response.status_code == 502
