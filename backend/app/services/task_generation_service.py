from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..utils.ai.llm import get_chat_model
from ..utils.ai.prompts import TASK_GENERATION_PROMPT
from ..models.study_plan import StudyPlan
from ..repositories.plan_repository import PlanRepository
from ..repositories.task_repository import TaskRepository
from ..schemas.study_task import GeneratedTaskList, StudyTaskCreate, StudyTaskRead


class TaskGenerationService:
    def __init__(self, db: Session) -> None:
        self.plan_repo = PlanRepository(db)
        self.task_repo = TaskRepository(db)

    def generate_tasks(self, plan_id: int) -> list[StudyTaskRead]:
        plan = self.plan_repo.get_by_id(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        result = self._invoke_llm(plan)

        if not result.tasks:
            raise HTTPException(
                status_code=502, detail="LLM returned no tasks for this plan"
            )

        created = [
            self.task_repo.create(
                plan_id,
                StudyTaskCreate(title=t.title, estimated_hours=t.estimated_hours),
            )
            for t in result.tasks
        ]
        return [StudyTaskRead.model_validate(t) for t in created]

    def _invoke_llm(self, plan: StudyPlan) -> GeneratedTaskList:
        due = (
            f"Due date: {plan.target_date.isoformat()}."
            if plan.target_date
            else "No due date."
        )
        messages = TASK_GENERATION_PROMPT.format_messages(
            goal=plan.goal,
            hours_per_week=plan.hours_per_week,
            due=due,
        )
        model = get_chat_model().with_structured_output(GeneratedTaskList)
        try:
            return model.invoke(messages)
        except Exception as exc:  # noqa: BLE001 — surface any LLM/parse failure as 502
            raise HTTPException(
                status_code=502, detail="Failed to generate tasks from the LLM"
            ) from exc
