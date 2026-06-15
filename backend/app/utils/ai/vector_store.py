"""Per-plan FAISS vector store helpers.

Each plan gets its own on-disk FAISS index under FAISS_INDEX_DIR/plan_{id}/.
Isolating by directory guarantees a plan's chat can never retrieve another
plan's document chunks.
"""

from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from ...core.config import settings
from .embeddings import get_embeddings


def index_path(plan_id: int) -> Path:
    return Path(settings.FAISS_INDEX_DIR) / f"plan_{plan_id}"


def _exists(plan_id: int) -> bool:
    # FAISS.save_local writes index.faiss + index.pkl
    return (index_path(plan_id) / "index.faiss").exists()


def load_index(plan_id: int) -> FAISS | None:
    """Load a plan's FAISS index, or None if it has no documents yet."""
    if not _exists(plan_id):
        return None
    return FAISS.load_local(
        str(index_path(plan_id)),
        get_embeddings(),
        allow_dangerous_deserialization=True,
    )


def add_documents(plan_id: int, docs: list[Document]) -> None:
    """Add chunks to a plan's index, creating it on first upload."""
    store = load_index(plan_id)
    if store is None:
        store = FAISS.from_documents(docs, get_embeddings())
    else:
        store.add_documents(docs)
    path = index_path(plan_id)
    path.mkdir(parents=True, exist_ok=True)
    store.save_local(str(path))


def similarity_search(plan_id: int, query: str, k: int = 4) -> list[Document]:
    """Return the k most relevant chunks for a plan, or [] if no index exists."""
    store = load_index(plan_id)
    if store is None:
        return []
    return store.similarity_search(query, k=k)


def similarity_search_with_score(
    plan_id: int, query: str, k: int = 4
) -> list[tuple[Document, float]]:
    """Like ``similarity_search`` but also returns FAISS L2 distances.

    Lower scores mean a closer match. Returns [] if the plan has no index yet,
    letting callers distinguish "no documents" from "documents but no match".
    """
    store = load_index(plan_id)
    if store is None:
        return []
    return store.similarity_search_with_score(query, k=k)
