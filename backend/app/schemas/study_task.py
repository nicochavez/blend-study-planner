from pydantic import BaseModel, Field


class StudyTaskCreate(BaseModel):
    title: str
    estimated_hours: float


class GeneratedTask(BaseModel):
    """A single task produced by the LLM (strict structured output)."""

    title: str = Field(description="Short, actionable study task title")
    estimated_hours: float = Field(
        gt=0, le=100, description="Estimated effort in hours, must be positive"
    )


class GeneratedTaskList(BaseModel):
    """Top-level structured output the LLM must return."""

    tasks: list[GeneratedTask] = Field(description="Ordered list of study tasks")


class StudyTaskUpdate(BaseModel):
    completed: bool


class StudyTaskRead(BaseModel):
    id: int
    plan_id: int
    title: str
    estimated_hours: float
    completed: bool

    model_config = {"from_attributes": True}
