from fastapi import Depends
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..services.chat_service import ChatService
from ..services.document_service import DocumentService
from ..services.plan_service import PlanService
from ..services.task_generation_service import TaskGenerationService
from ..services.task_service import TaskService
from ..services.user_service import UserService
from ..utils.ai.checkpointer import get_checkpointer


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


def get_plan_service(db: Session = Depends(get_db)) -> PlanService:
    return PlanService(db)


def get_task_service(db: Session = Depends(get_db)) -> TaskService:
    return TaskService(db)


def get_task_generation_service(
    db: Session = Depends(get_db),
) -> TaskGenerationService:
    return TaskGenerationService(db)


def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    return DocumentService(db)


def get_chat_service(
    db: Session = Depends(get_db),
    checkpointer: BaseCheckpointSaver = Depends(get_checkpointer),
) -> ChatService:
    return ChatService(db, checkpointer)
