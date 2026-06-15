"""Local embeddings (fastembed) so RAG needs no extra API key."""

from functools import lru_cache

from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_core.embeddings import Embeddings

from ...core.config import settings


@lru_cache
def get_embeddings() -> Embeddings:
    """Return a cached local embedding model.

    Cached because the underlying ONNX model is expensive to load.
    """
    return FastEmbedEmbeddings(model_name=settings.EMBEDDING_MODEL)
