"""Prompt templates for AI-driven study plan features."""

from langchain_core.prompts import ChatPromptTemplate

RAG_SYSTEM_PROMPT = (
    "You are a study assistant that answers questions about a user's uploaded "
    "study documents. Use ONLY the information in the context below to answer. "
    "If the context is empty or does not contain the answer, say you don't have "
    "enough information in the uploaded documents to answer that — do not use "
    "outside knowledge and do not guess. You may use the earlier conversation for "
    "follow-up questions, but ground every factual claim in the context.\n\n"
    "Context:\n{context}"
)

NO_CONTEXT_PLACEHOLDER = "(no relevant content was found in the uploaded documents)"

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
