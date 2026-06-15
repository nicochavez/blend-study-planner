from fastapi import HTTPException
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.orm import Session

from ..repositories.plan_repository import PlanRepository
from ..schemas.study_document import ChatRequest, ChatResponse, Source
from ..utils.ai.rag_graph import build_rag_graph


def _as_text(content) -> str:
    """Flatten an LLM message's content (str or list of blocks) to text."""
    if isinstance(content, str):
        return content
    parts = [
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return "".join(parts)


class ChatService:
    def __init__(self, db: Session, checkpointer: BaseCheckpointSaver) -> None:
        self.plan_repo = PlanRepository(db)
        self.graph = build_rag_graph(checkpointer)

    def ask(self, plan_id: int, req: ChatRequest) -> ChatResponse:
        if not self.plan_repo.get_by_id(plan_id):
            raise HTTPException(status_code=404, detail="Plan not found")

        thread_id = req.conversation_id or f"plan_{plan_id}"
        try:
            result = self.graph.invoke(
                {"messages": [HumanMessage(req.question)], "plan_id": plan_id},
                {"configurable": {"thread_id": thread_id}},
            )
        except Exception as exc:  # noqa: BLE001 — surface LLM/graph failures as 502
            raise HTTPException(
                status_code=502, detail="Failed to answer from the documents"
            ) from exc

        answer = _as_text(result["messages"][-1].content)
        sources = [Source(**s) for s in result.get("sources", [])]
        return ChatResponse(answer=answer, sources=sources, grounded=bool(sources))
