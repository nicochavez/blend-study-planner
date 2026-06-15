"""Deep Agent for US3 — multi-step study plan generation.

Wraps ``deepagents.create_deep_agent`` with the planning tools and a system
prompt that drives the decompose -> retrieve -> generate -> validate ->
submit loop. The agent's built-in scratchpad (``DeepAgentState.files``) is
checkpointed per-thread by the supplied checkpointer, giving us a working
scratchpad without any extra backend wiring.
"""

from deepagents import create_deep_agent
from langchain_core.language_models import LanguageModelLike
from langgraph.checkpoint.base import BaseCheckpointSaver

from ...core.config import settings
from .prompts import PLANNING_AGENT_SYSTEM_PROMPT


def build_planning_agent(
    tools: list,
    model: LanguageModelLike,
    checkpointer: BaseCheckpointSaver,
    budget_hours: float,
):
    instructions = PLANNING_AGENT_SYSTEM_PROMPT.format(
        budget_hours=budget_hours,
        tolerance=settings.PLAN_HOURS_TOLERANCE,
        max_subtopics=settings.AGENT_MAX_SUBTOPICS,
    )
    return create_deep_agent(
        tools=tools,
        instructions=instructions,
        model=model,
        checkpointer=checkpointer,
    )
