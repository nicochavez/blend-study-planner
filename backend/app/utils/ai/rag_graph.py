"""A small LangGraph RAG chat graph: retrieve plan chunks, then answer.

The graph is stateful: compiled with a checkpointer, it persists the message
history per ``thread_id`` so a conversation about a plan's documents supports
follow-up questions. Retrieval is scoped to a single plan, keeping document data
isolated between plans.
"""

from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from ...core.config import settings
from .llm import get_chat_model
from .prompts import NO_CONTEXT_PLACEHOLDER, RAG_SYSTEM_PROMPT
from .vector_store import similarity_search_with_score


class ChatState(TypedDict):
    messages: Annotated[list, add_messages]
    plan_id: int
    context: str
    sources: list[dict]


def _latest_question(messages: list) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return message.content
    return ""


def _retrieve(state: ChatState) -> dict:
    """Pull the most relevant chunks for this plan and the latest question."""
    question = _latest_question(state["messages"])
    scored = similarity_search_with_score(
        state["plan_id"], question, k=settings.RAG_TOP_K
    )
    relevant = [
        doc for doc, score in scored if score <= settings.RAG_SCORE_THRESHOLD
    ]

    sources = [
        {
            "document_id": doc.metadata.get("document_id"),
            "filename": doc.metadata.get("filename", "unknown"),
            "page": doc.metadata.get("page", 0),
            "snippet": doc.page_content[:200],
        }
        for doc in relevant
    ]
    context = "\n\n---\n\n".join(doc.page_content for doc in relevant)
    return {"context": context or NO_CONTEXT_PLACEHOLDER, "sources": sources}


def _generate(state: ChatState) -> dict:
    """Answer the question grounded in the retrieved context + conversation."""
    system = SystemMessage(RAG_SYSTEM_PROMPT.format(context=state["context"]))
    reply = get_chat_model().invoke([system, *state["messages"]])
    return {"messages": [reply]}


def build_rag_graph(checkpointer: BaseCheckpointSaver):
    """Compile the retrieve -> generate chat graph with the given checkpointer."""
    builder = StateGraph(ChatState)
    builder.add_node("retrieve", _retrieve)
    builder.add_node("generate", _generate)
    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", END)
    return builder.compile(checkpointer=checkpointer)
