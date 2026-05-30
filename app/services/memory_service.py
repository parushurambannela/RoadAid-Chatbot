"""
memory_service.py

Manages per-session conversation history.

Storage: in-memory dict (fast, zero dependencies).
Swap-out path: replace _store with a Redis or MongoDB-backed implementation
without changing any other file — the interface stays the same.

Session lifecycle:
  - Created automatically on the first question if no session_id is given.
  - Kept alive as long as the server is running.
  - Cleared explicitly via DELETE /api/v1/chat/{session_id}/history.
"""

import uuid
import logging
from typing import Optional
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

logger = logging.getLogger(__name__)

# session_id  →  list of alternating HumanMessage / AIMessage
_store: dict[str, list[BaseMessage]] = {}

# How many past exchanges (human + AI pairs) to include in the prompt.
# Keeping this small avoids blowing the context window.
MAX_HISTORY_PAIRS = 5


def get_or_create_session(session_id: Optional[str] = None) -> str:
    """
    Return an existing session_id, or create a new one.
    Call this at the start of every request.
    """
    if session_id and session_id in _store:
        logger.debug("Resuming session: %s  (%d messages so far)",
                     session_id, len(_store[session_id]))
        return session_id

    new_id = session_id or str(uuid.uuid4())
    _store[new_id] = []
    logger.debug("New session created: %s", new_id)
    return new_id


def add_exchange(session_id: str, question: str, answer: str) -> None:
    """
    Save one human-question + AI-answer pair to the session.
    Called after every successful response.
    """
    if session_id not in _store:
        _store[session_id] = []

    _store[session_id].append(HumanMessage(content=question))
    _store[session_id].append(AIMessage(content=answer))
    logger.debug("Saved exchange to session %s  (total messages: %d)",
                 session_id, len(_store[session_id]))


def get_history(session_id: str) -> list[BaseMessage]:
    """Return all messages for a session (empty list if not found)."""
    return _store.get(session_id, [])


def format_history_for_prompt(session_id: str) -> str:
    """
    Format the last N exchanges as a plain-text string to inject into prompts.

    Example output:
        Human: Show all active drivers
        AI: There are 4 active drivers: Mohan Das, Ravi Kumar...

        Human: How many are assigned to NH44?
        AI: 2 drivers are currently assigned to NH44.
    """
    messages = get_history(session_id)
    if not messages:
        return "No previous conversation."

    # Keep only the last MAX_HISTORY_PAIRS pairs = MAX_HISTORY_PAIRS * 2 messages
    recent = messages[-(MAX_HISTORY_PAIRS * 2):]

    lines = []
    for msg in recent:
        if isinstance(msg, HumanMessage):
            lines.append(f"Human: {msg.content}")
        elif isinstance(msg, AIMessage):
            lines.append(f"AI: {msg.content}\n")

    return "\n".join(lines).strip()


def get_history_as_dicts(session_id: str) -> list[dict]:
    """
    Return history as a list of plain dicts — used by the API response.

    Example:
        [{"role": "human", "content": "..."}, {"role": "ai", "content": "..."}]
    """
    messages = get_history(session_id)
    result = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            result.append({"role": "human", "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"role": "ai", "content": msg.content})
    return result


def clear_session(session_id: str) -> bool:
    """
    Clear all messages for a session.
    Returns True if the session existed, False if it didn't.
    """
    if session_id in _store:
        _store.pop(session_id)
        logger.debug("Cleared session: %s", session_id)
        return True
    return False


def list_sessions() -> list[dict]:
    """Debug helper — returns all active sessions and their message counts."""
    return [
        {"session_id": sid, "message_count": len(msgs)}
        for sid, msgs in _store.items()
    ]
