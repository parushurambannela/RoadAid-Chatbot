"""
chat_service.py

Orchestrates the full chat pipeline with conversation memory:
  1. Retrieve conversation history for this session
  2. Generate MongoDB query from question + history (Gemini 2.5 Pro)
  3. Execute query against MongoDB
  4. Generate human-readable answer from results + history (Gemini 2.5 Pro)
  5. Save the exchange to memory
"""

import os
import json
import logging
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from app.services.query_service import generate_mongo_query, execute_mongo_query
from app.services import memory_service
from app.prompts.mongo_prompts import ANSWER_GENERATION_PROMPT

logger = logging.getLogger(__name__)


def _build_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-pro"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.3,
    )


def answer_question(question: str, session_id: Optional[str] = None) -> dict:
    """
    Full pipeline: question → (history-aware) query → execute → answer → save.

    Args:
        question  : The user's current question.
        session_id: Optional existing session ID. If None, a new session is created.

    Returns a dict with:
      - answer     : human-readable string
      - query      : the generated MongoDB query dict
      - data       : raw list of results from MongoDB
      - session_id : the session ID (new or existing) — client must send this back
      - error      : error message if something went wrong (optional)
    """

    # ── 0. Get / create session and fetch history ──────────────────────────
    session_id = memory_service.get_or_create_session(session_id)
    history = memory_service.format_history_for_prompt(session_id)
    logger.info("Session: %s | Question: %s", session_id, question)
    logger.debug("History passed to LLM:\n%s", history)

    # ── 1. Generate the MongoDB query (history-aware) ──────────────────────
    try:
        query_dict = generate_mongo_query(question, history)
        
        logger.info("Generated query: %s", query_dict)
    except Exception as exc:
        logger.error("Query generation failed: %s", exc)
        return {
            "answer": "Sorry, I could not understand your question well enough to query the database.",
            "query": {},
            "data": [],
            "session_id": session_id,
            "error": str(exc),
        }

    # ── 2. Execute the query ───────────────────────────────────────────────
    try:
        results = execute_mongo_query(query_dict)
        logger.info("Query returned %d result(s)", len(results))
    except ValueError as exc:
        logger.warning("Query rejected by validator: %s", exc)
        return {
            "answer": f"The query could not be executed: {exc}",
            "query": query_dict,
            "data": [],
            "session_id": session_id,
            "error": str(exc),
        }
    except Exception as exc:
        logger.error("Query execution error: %s", exc)
        return {
            "answer": "There was an error executing the database query. Please try again.",
            "query": query_dict,
            "data": [],
            "session_id": session_id,
            "error": str(exc),
        }

    # ── 3. Generate a human-readable answer (history-aware) ───────────────
    try:
        llm = _build_llm()
        results_str = json.dumps(results, indent=2, default=str)
        query_str = json.dumps(query_dict, indent=2)

        prompt_text = ANSWER_GENERATION_PROMPT.format(
            history=history,
            question=question,
            query=query_str,
            results=results_str,
        )

        response = llm.invoke([HumanMessage(content=prompt_text)])
        answer = response.content.strip()
        logger.debug("Generated answer: %s", answer[:200])

    except Exception as exc:
        logger.error("Answer generation failed: %s", exc)
        answer = "I retrieved the data but could not generate a readable summary."

    # ── 4. Save exchange to memory ─────────────────────────────────────────
    memory_service.add_exchange(session_id, question, answer)

    return {
        "answer": answer,
        "query": query_dict,
        "data": results,
        "session_id": session_id,
    }
