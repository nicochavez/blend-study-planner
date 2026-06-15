from fastapi import APIRouter, Depends, File, UploadFile

from ...schemas.study_document import ChatRequest, ChatResponse, StudyDocumentRead
from ...schemas.study_plan import StudyPlanCreate, StudyPlanRead, StudyPlanUpdate
from ...schemas.study_task import StudyTaskCreate, StudyTaskRead, StudyTaskUpdate
from ...services.chat_service import ChatService
from ...services.document_service import DocumentService
from ...services.planning_agent_service import PlanningAgentService
from ...services.plan_service import PlanService
from ...services.task_generation_service import TaskGenerationService
from ...services.task_service import TaskService
from ..deps import (
    get_chat_service,
    get_document_service,
    get_plan_service,
    get_planning_agent_service,
    get_task_generation_service,
    get_task_service,
)

router = APIRouter(prefix="/plans", tags=["plans"])


@router.post("", response_model=StudyPlanRead, status_code=201)
def create_plan(data: StudyPlanCreate, svc: PlanService = Depends(get_plan_service)):
    return svc.create_plan(data)


@router.get("/{plan_id}", response_model=StudyPlanRead)
def get_plan(plan_id: int, svc: PlanService = Depends(get_plan_service)):
    return svc.get_plan(plan_id)


@router.patch("/{plan_id}", response_model=StudyPlanRead)
def update_plan(
    plan_id: int,
    data: StudyPlanUpdate,
    svc: PlanService = Depends(get_plan_service),
):
    return svc.update_plan(plan_id, data)


@router.post("/{plan_id}/tasks", response_model=StudyTaskRead, status_code=201)
def create_task(
    plan_id: int, data: StudyTaskCreate, svc: TaskService = Depends(get_task_service)
):
    return svc.create_task(plan_id, data)


@router.get("/{plan_id}/tasks", response_model=list[StudyTaskRead])
def get_tasks(plan_id: int, svc: TaskService = Depends(get_task_service)):
    return svc.get_tasks_by_plan(plan_id)


@router.post(
    "/{plan_id}/generate-tasks",
    response_model=list[StudyTaskRead],
    status_code=201,
)
def generate_tasks(
    plan_id: int,
    svc: TaskGenerationService = Depends(get_task_generation_service),
):
    return svc.generate_tasks(plan_id)


@router.post(
    "/{plan_id}/agent-plan",
    response_model=list[StudyTaskRead],
    status_code=201,
)
def agent_plan(
    plan_id: int,
    svc: PlanningAgentService = Depends(get_planning_agent_service),
):
    return svc.generate_plan(plan_id)


@router.patch("/{plan_id}/tasks/{task_id}", response_model=StudyTaskRead)
def update_task(
    plan_id: int,
    task_id: int,
    data: StudyTaskUpdate,
    svc: TaskService = Depends(get_task_service),
):
    return svc.update_task(plan_id, task_id, data)


@router.post(
    "/{plan_id}/documents",
    response_model=StudyDocumentRead,
    status_code=201,
)
def upload_document(
    plan_id: int,
    file: UploadFile = File(...),
    svc: DocumentService = Depends(get_document_service),
):
    return svc.upload_document(plan_id, file)


@router.get("/{plan_id}/documents", response_model=list[StudyDocumentRead])
def list_documents(
    plan_id: int, svc: DocumentService = Depends(get_document_service)
):
    return svc.list_documents(plan_id)


@router.post("/{plan_id}/chat", response_model=ChatResponse)
def chat(
    plan_id: int,
    data: ChatRequest,
    svc: ChatService = Depends(get_chat_service),
):
    return svc.ask(plan_id, data)
