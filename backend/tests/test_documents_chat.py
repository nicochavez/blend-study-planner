"""Tests for US2 — per-plan document chat (RAG) with conversation memory.

Runs fully offline: fake deterministic embeddings (no model download), a mocked
chat model, an in-memory LangGraph checkpointer, and a temp FAISS directory.
"""

import hashlib

import pytest
from app.api.deps import get_checkpointer
from app.core.config import settings
from app.main import app
from app.utils.ai import rag_graph, vector_store
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

_DOC_TEXT = (
    "The capital of France is Paris. Paris sits on the river Seine and is "
    "famous for the Eiffel Tower and the Louvre museum."
)


class _FakeEmbeddings(Embeddings):
    """Deterministic bag-of-words vectors so FAISS works without a real model."""

    dim = 64

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for tok in text.lower().split():
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0
        return v

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


class _FakeChatModel:
    """Records the messages it receives so tests can assert on memory."""

    def __init__(self):
        self.calls: list[list] = []

    def invoke(self, messages):
        self.calls.append(list(messages))
        return AIMessage(content="The capital of France is Paris.")


@pytest.fixture(autouse=True)
def ai_env(monkeypatch, tmp_path):
    """Isolate FAISS to a temp dir and stub out embeddings, LLM, checkpointer."""
    monkeypatch.setattr(settings, "FAISS_INDEX_DIR", str(tmp_path))
    # Keep every retrieved chunk regardless of the fake embeddings' distances.
    monkeypatch.setattr(settings, "RAG_SCORE_THRESHOLD", 1e9)

    monkeypatch.setattr(vector_store, "get_embeddings", _FakeEmbeddings)

    fake_chat = _FakeChatModel()
    monkeypatch.setattr(rag_graph, "get_chat_model", lambda: fake_chat)

    saver = InMemorySaver()
    app.dependency_overrides[get_checkpointer] = lambda: saver
    yield fake_chat
    app.dependency_overrides.pop(get_checkpointer, None)


def _make_plan(client, goal="Learn geography"):
    user = client.post("/users", json={"name": f"u{id(goal)}"}).json()
    return client.post(
        "/plans",
        json={"user_id": user["id"], "goal": goal, "hours_per_week": 5.0},
    ).json()


def _upload(client, plan_id, text=_DOC_TEXT, name="notes.txt", ctype="text/plain"):
    return client.post(
        f"/plans/{plan_id}/documents",
        files={"file": (name, text.encode(), ctype)},
    )


def test_upload_persists_and_indexes(client):
    plan = _make_plan(client)
    resp = _upload(client, plan["id"])
    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "notes.txt"
    assert body["status"] == "indexed"
    assert body["num_chunks"] >= 1

    listed = client.get(f"/plans/{plan['id']}/documents").json()
    assert len(listed) == 1
    assert listed[0]["id"] == body["id"]


def test_upload_unsupported_type_is_400(client):
    plan = _make_plan(client)
    resp = client.post(
        f"/plans/{plan['id']}/documents",
        files={"file": ("pic.png", b"\x89PNG", "image/png")},
    )
    assert resp.status_code == 400


def test_upload_plan_not_found_is_404(client):
    resp = _upload(client, 999)
    assert resp.status_code == 404


def test_chat_grounded_answer_with_sources(client):
    plan = _make_plan(client)
    _upload(client, plan["id"])

    resp = client.post(
        f"/plans/{plan['id']}/chat",
        json={"question": "What is the capital of France?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["grounded"] is True
    assert body["answer"]
    assert len(body["sources"]) >= 1
    assert body["sources"][0]["filename"] == "notes.txt"


def test_chat_without_documents_is_not_grounded(client):
    plan = _make_plan(client)
    resp = client.post(
        f"/plans/{plan['id']}/chat",
        json={"question": "What is the capital of France?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["grounded"] is False
    assert body["sources"] == []


def test_chat_remembers_previous_turn(client, ai_env):
    plan = _make_plan(client)
    _upload(client, plan["id"])

    client.post(
        f"/plans/{plan['id']}/chat",
        json={"question": "What is the capital of France?"},
    )
    client.post(
        f"/plans/{plan['id']}/chat",
        json={"question": "What river does it sit on?"},
    )

    # The second LLM call must have seen the first turn (human + ai) as memory.
    second_call = ai_env.calls[1]
    humans = [m.content for m in second_call if isinstance(m, HumanMessage)]
    assert "What is the capital of France?" in humans
    assert "What river does it sit on?" in humans
    assert any(isinstance(m, AIMessage) for m in second_call)


def test_documents_are_isolated_per_plan(client):
    plan_a = _make_plan(client, goal="France")
    plan_b = _make_plan(client, goal="Spain")
    _upload(client, plan_a["id"])  # only plan A has documents

    resp = client.post(
        f"/plans/{plan_b['id']}/chat",
        json={"question": "What is the capital of France?"},
    )
    body = resp.json()
    assert body["grounded"] is False
    assert body["sources"] == []


def test_chat_plan_not_found_is_404(client):
    resp = client.post("/plans/999/chat", json={"question": "hi"})
    assert resp.status_code == 404
