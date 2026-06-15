import logging
import uuid

from fastapi import HTTPException
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.study_plan import StudyPlan
from ..repositories.plan_repository import PlanRepository
from ..repositories.task_repository import TaskRepository
from ..schemas.study_plan_agent import PlanTaskDraft
from ..schemas.study_task import StudyTaskCreate, StudyTaskRead
from ..utils.ai.llm import get_chat_model
from ..utils.ai.planning_agent import build_planning_agent
from ..utils.ai.planning_tools import build_planning_tools, compute_budget_hours
from ..utils.ai.planning_tools import validate_constraints as _validate_constraints

logger = logging.getLogger(__name__)


def _goal_message(plan: StudyPlan, budget_hours: float) -> HumanMessage:
    due = (
        f"Target date: {plan.target_date.isoformat()}."
        if plan.target_date
        else "No target date."
    )
    return HumanMessage(
        f"Goal: {plan.goal}\n"
        f"Available time: {plan.hours_per_week} hours per week.\n"
        f"{due}\n"
        f"Total hours budget for this plan: {budget_hours}."
    )


class PlanningAgentService:
    def __init__(self, db: Session, checkpointer: BaseCheckpointSaver) -> None:
        self.plan_repo = PlanRepository(db)
        self.task_repo = TaskRepository(db)
        self.checkpointer = checkpointer

    def generate_plan(self, plan_id: int) -> list[StudyTaskRead]:
        plan = self.plan_repo.get_by_id(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        budget_hours = compute_budget_hours(plan)
        result: dict = {}
        tools = build_planning_tools(plan_id, plan.goal, budget_hours, result)
        agent = build_planning_agent(
            tools, get_chat_model(), None, budget_hours
        )

        thread_id = f"plan_{plan_id}:gen:{uuid.uuid4()}"
        try:
            agent.invoke(
                {"messages": [_goal_message(plan, budget_hours)]},
                {
                    "configurable": {"thread_id": thread_id},
                    "recursion_limit": settings.AGENT_RECURSION_LIMIT,
                },
            )
        except Exception as exc:  # noqa: BLE001 — surface agent/LLM failures as 502
            logger.exception("Planning agent invoke failed for plan %s", plan_id)
            raise HTTPException(
                status_code=502, detail="Planning agent failed to generate a plan"
            ) from exc

        if "tasks" not in result:
            logger.error(
                "Planning agent for plan %s finished without calling submit_plan",
                plan_id,
            )
            raise HTTPException(
                status_code=502,
                detail="Planning agent did not submit a plan",
            )

        # Defense in depth: re-validate the submitted plan before persisting.
        drafts = [PlanTaskDraft(**t) for t in result["tasks"]]
        validation = _validate_constraints(drafts, result["subtopics"], budget_hours)
        if not validation.ok:
            raise HTTPException(
                status_code=422,
                detail=f"Agent could not satisfy plan constraints: {validation.issues}",
            )

        created = [
            self.task_repo.create(
                plan_id,
                StudyTaskCreate(title=t.title, estimated_hours=t.estimated_hours),
            )
            for t in drafts
        ]
        return [StudyTaskRead.model_validate(t) for t in created]
