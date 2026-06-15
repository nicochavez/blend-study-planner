"""Single place to construct the chat model so it is easy to configure and mock."""

from functools import lru_cache

from langchain_anthropic import ChatAnthropic

from ...core.config import settings


@lru_cache
def get_chat_model() -> ChatAnthropic:
    """Return a configured Claude chat model.

    Centralizing construction here means tests can monkeypatch this single
    function instead of reaching into every service.
    """
    return ChatAnthropic(
        model=settings.ANTHROPIC_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
        temperature=settings.LLM_TEMPERATURE,
        timeout=60,
        max_retries=2,
    )
