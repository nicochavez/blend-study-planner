from pydantic import BaseModel, Field


class PlanTaskDraft(BaseModel):
    """A task drafted by the planning agent, tagged with its subtopic."""

    title: str
    estimated_hours: float = Field(
        gt=0, le=100, description="Estimated effort in hours, must be positive"
    )
    subtopic: str


class ValidationResult(BaseModel):
    """Result of checking draft tasks against the plan's hours/scope constraints."""

    ok: bool
    total_hours: float
    budget_hours: float
    over_by: float
    issues: list[str]
