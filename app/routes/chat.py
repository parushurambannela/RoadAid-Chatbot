from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional
import logging

from app.services.chat_service import answer_question
from app.services import memory_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural language question about the RoadAid database",
        examples=["How many accidents happened this month?"],
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Pass the session_id from the previous response to continue a conversation. "
                    "Omit (or send null) to start a fresh session.",
    )


class ChatResponse(BaseModel):
    answer: str
    query: dict
    data: list[Any]
    session_id: str = Field(description="Send this back in the next request to maintain conversation history.")
    error: Optional[str] = None


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[dict]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse,
             summary="Ask a question about the RoadAid database")
async def chat(request: ChatRequest):
    """
    Accepts a natural language question and returns:
    - **answer**     : human-readable response from Gemini 2.5 Pro
    - **query**      : the MongoDB query that was generated
    - **data**       : raw results from the database
    - **session_id** : pass this back in the next request to continue the conversation

    **How to use conversation memory:**
    ```
    # First message — no session_id needed
    POST /chat  { "question": "Show all active drivers" }
    → { "answer": "...", "session_id": "abc-123", ... }

    # Follow-up — send the session_id back
    POST /chat  { "question": "How many are on NH44?", "session_id": "abc-123" }
    → { "answer": "2 drivers are on NH44...", "session_id": "abc-123", ... }
    ```
    """
    logger.info("POST /chat | session=%s | question=%s",
                request.session_id or "NEW", request.question)

    result = answer_question(request.question, request.session_id)

    if result.get("error") and not result.get("data") and not result.get("answer"):
        raise HTTPException(status_code=500, detail=result["error"])

    return ChatResponse(**result)


@router.get("/chat/{session_id}/history", response_model=HistoryResponse,
            summary="View conversation history for a session")
async def get_history(session_id: str):
    """
    Returns the full conversation history for a given session_id.
    Useful for building a chat UI that renders previous messages.
    """
    messages = memory_service.get_history_as_dicts(session_id)
    if not messages:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found or has no history."
        )
    return HistoryResponse(session_id=session_id, messages=messages)


@router.delete("/chat/{session_id}/history", summary="Clear conversation history for a session")
async def clear_history(session_id: str):
    """
    Clears all conversation history for a session.
    The session_id can be reused — it will start fresh.
    """
    cleared = memory_service.clear_session(session_id)
    if not cleared:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found."
        )
    logger.info("Cleared history for session: %s", session_id)
    return {"message": f"History cleared for session '{session_id}'."}
