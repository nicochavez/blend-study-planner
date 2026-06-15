"""Tools for the planning agent (US3).

Each tool is a thin wrapper over existing AI utilities. ``plan_id``, the
plan's goal, and its hours budget are bound per-request via closures in
``build_planning_tools`` so the model never has to supply them.
"""

import math
from datetime import date

from langchain_core.tools import tool

from ...core.config import settings
from ...models.study_plan import StudyPlan
from ...schemas.study_plan_agent import PlanTaskDraft, ValidationResult
from ...schemas.study_task import GeneratedTaskList
from .llm import get_chat_model
from .prompts import NO_CONTEXT_PLACEHOLDER, SUBTOPIC_TASK_GENERATION_PROMPT
from .vector_store import similarity_search


def compute_budget_hours(plan: StudyPlan) -> float:
    """Hours budget for a plan, per the rules in the planning agent spec.

    If the plan has a target_date, the budget scales with the number of
    weeks until then. Otherwise, hours_per_week is treated as a soft weekly
    cap projected over DEFAULT_PLAN_WEEKS.
    """
    if plan.target_date:
        days = (plan.target_date - date.today()).days
        weeks = max(1, math.ceil(days / 7))
        return plan.hours_per_week * weeks
    return plan.hours_per_week * settings.DEFAULT_PLAN_WEEKS


def validate_constraints(
    tasks: list[PlanTaskDraft], subtopics: list[str], budget_hours: float
) -> ValidationResult:
    """Check draft tasks against the hours budget and scope rules (pure, no LLM)."""
    issues: list[str] = []

    total_hours = sum(t.estimated_hours for t in tasks)
    max_hours = budget_hours * (1 + settings.PLAN_HOURS_TOLERANCE)
    over_by = max(0.0, total_hours - max_hours)

    if not tasks:
        issues.append("Plan has no tasks.")

    if not (2 <= len(subtopics) <= settings.AGENT_MAX_SUBTOPICS):
        issues.append(
            f"Expected 2-{settings.AGENT_MAX_SUBTOPICS} subtopics, "
            f"got {len(subtopics)}."
        )

    covered = {t.subtopic for t in tasks}
    missing = [s for s in subtopics if s not in covered]
    if missing:
        issues.append(f"Subtopics with no tasks: {missing}")

    if over_by > 0:
        issues.append(
            f"Total estimated hours ({total_hours}) exceeds the budget "
            f"({budget_hours}, +{settings.PLAN_HOURS_TOLERANCE:.0%} tolerance) "
            f"by {over_by}."
        )

    return ValidationResult(
        ok=not issues,
        total_hours=total_hours,
        budget_hours=budget_hours,
        over_by=over_by,
        issues=issues,
    )


def build_planning_tools(
    plan_id: int, goal: str, budget_hours: float, result: dict
) -> list:
    """Build the four agent tools, bound to this request's plan/budget.

    ``result`` is a mutable dict the ``submit_plan`` tool writes the final
    plan into, so the service can read it back after ``agent.invoke``.
    """

    @tool
    def retrieve_knowledge(query: str) -> str:
        """Search this plan's uploaded documents for content relevant to `query`."""
        docs = similarity_search(plan_id, query, k=settings.RAG_TOP_K)
        if not docs:
            return NO_CONTEXT_PLACEHOLDER
        return "\n\n---\n\n".join(doc.page_content for doc in docs)

    @tool
    def generate_tasks_for_subtopic(subtopic: str, hours_budget: float) -> list[dict]:
        """Generate candidate study tasks for one subtopic of the plan's goal.

        Returns a list of {title, estimated_hours} dicts.
        """
        docs = similarity_search(plan_id, subtopic, k=settings.RAG_TOP_K)
        context = (
            "\n\n---\n\n".join(doc.page_content for doc in docs)
            if docs
            else NO_CONTEXT_PLACEHOLDER
        )
        messages = SUBTOPIC_TASK_GENERATION_PROMPT.format_messages(
            goal=goal, subtopic=subtopic, hours_budget=hours_budget, context=context
        )
        model = get_chat_model().with_structured_output(GeneratedTaskList)
        generated = model.invoke(messages)
        return [t.model_dump() for t in generated.tasks]

    @tool("validate_constraints")
    def validate_constraints_tool(
        tasks: list[PlanTaskDraft], subtopics: list[str]
    ) -> ValidationResult:
        """Check draft tasks against this plan's hours budget and scope rules."""
        return validate_constraints(tasks, subtopics, budget_hours)

    @tool
    def submit_plan(subtopics: list[str], tasks: list[PlanTaskDraft]) -> str:
        """Submit the final subtopic breakdown and task list.

        Call this once `validate_constraints` reports ok=true. This is the
        only way to finish the planning job.
        """
        validation = validate_constraints(tasks, subtopics, budget_hours)
        result["subtopics"] = subtopics
        result["tasks"] = [t.model_dump() for t in tasks]
        result["validation"] = validation.model_dump()
        return (
            f"Submitted {len(tasks)} tasks across {len(subtopics)} subtopics. "
            f"ok={validation.ok}"
        )

    return [
        retrieve_knowledge,
        generate_tasks_for_subtopic,
        validate_constraints_tool,
        submit_plan,
    ]
