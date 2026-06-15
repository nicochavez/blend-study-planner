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
        # langchain-anthropic defaults max_tokens to 1024. That starves the
        # planning agent: each loop turn (reasoning + file writes + the final
        # submit_plan call carrying the whole task list) gets truncated at the
        # cap, the tool call comes back malformed, and the deep-agent loop
        # retries until it hits AGENT_RECURSION_LIMIT — burning tokens without
        # ever submitting a plan. Give every turn real output headroom.
        max_tokens=settings.LLM_MAX_TOKENS,
        timeout=60,
        max_retries=2,
    )
