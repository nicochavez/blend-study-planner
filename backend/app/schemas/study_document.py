from datetime import datetime

from pydantic import BaseModel, Field


class StudyDocumentRead(BaseModel):
    id: int
    plan_id: int
    filename: str
    content_type: str
    size_bytes: int
    num_chunks: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, description="Question about the plan's documents")
    conversation_id: str | None = Field(
        default=None,
        description=(
            "Conversation/thread key for multi-turn memory. Defaults to the plan's "
            "own thread (plan_{id}); supply your own to keep separate conversations."
        ),
    )


class Source(BaseModel):
    """A document chunk that grounded part of the answer."""

    document_id: int
    filename: str
    page: int
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    grounded: bool = Field(
        description="True when the answer is backed by retrieved document chunks."
    )
