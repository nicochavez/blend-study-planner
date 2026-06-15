"""Prompt templates for AI-driven study plan features."""

from langchain_core.prompts import ChatPromptTemplate

TASK_GENERATION_SYSTEM_PROMPT = (
    "You are an expert study coach. Given a study goal, a weekly time budget, "
    "and an optional due date, break the goal into a sequence of concrete, "
    "actionable study tasks. Order tasks logically (fundamentals first). "
    "Keep each task's estimated_hours realistic and make the total roughly "
    "consistent with the time available."
)

TASK_GENERATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", TASK_GENERATION_SYSTEM_PROMPT),
        (
            "human",
            "Goal: {goal}\n"
            "Available time: {hours_per_week} hours per week.\n"
            "{due}",
        ),
    ]
)
