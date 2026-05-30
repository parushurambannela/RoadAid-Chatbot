"""
query_service.py

Handles the two-step LangChain pipeline:
  1. Ask Gemini 2.5 Pro to generate a MongoDB query from the user's question.
  2. Execute the query safely against MongoDB.
"""

import os
import ast
import json
import logging
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId, Decimal128

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from app.database.mongo_client import get_sync_db
from app.prompts.mongo_prompts import QUERY_GENERATION_PROMPT
from app.schemas.schema_loader import get_all_schemas_text
from app.utils.query_validator import validate_query, sanitize_filter

logger = logging.getLogger(__name__)

MAX_RESULTS = 50


def _sanitize_doc(obj: Any) -> Any:
    """
    Recursively convert BSON types that Pydantic/JSON can't serialize.

    Handles the full document tree — not just the top-level _id — because
    MongoDB documents often contain ObjectId references in nested fields
    (e.g. driverId, userId, roadId) and Decimal128 monetary values.
    """
    if isinstance(obj, dict):
        return {k: _sanitize_doc(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_doc(item) for item in obj]
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, Decimal128):
        return float(obj.to_decimal())
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def _build_llm() -> ChatGoogleGenerativeAI:
    """Instantiate the Gemini 2.5 Pro LLM."""
    return ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-pro"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0,
    )


def _parse_llm_output(raw: str) -> dict:
    """Parse the raw LLM string into a Python dict. Tries JSON then ast.literal_eval."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError) as exc:
        raise ValueError(f"Could not parse LLM output as a query dict: {raw!r}") from exc


def _inject_date_context(question: str) -> str:
    """Prepend today's date so the LLM can resolve 'today', 'this month', etc."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"[Today's date: {today}] {question}"


def generate_mongo_query(question: str, history: str = "") -> dict:
    """
    Convert a natural-language question into a MongoDB query descriptor dict.

    All 122 collection schemas are sent with every prompt so the LLM has
    full visibility — Gemini 2.5 Pro's 1M-token context window makes this
    trivial and avoids the complexity of semantic routing.
    """
    llm = _build_llm()
    question_with_date = _inject_date_context(question)

    all_schemas = get_all_schemas_text()
    logger.debug("Sending all schemas to LLM (%d chars)", len(all_schemas))

    prompt_text = QUERY_GENERATION_PROMPT.format(
        schemas=all_schemas,
        history=history or "No previous conversation.",
        question=question_with_date,
    )

    response = _build_llm().invoke([HumanMessage(content=prompt_text)])
    raw_output = response.content

    logger.debug("Raw LLM query output: %s", raw_output)
    return _parse_llm_output(raw_output)


def execute_mongo_query(query_dict: dict) -> list[dict]:
    """Execute a validated query dict against MongoDB. Returns plain dicts."""
    is_safe, reason = validate_query(query_dict)
    if not is_safe:
        raise ValueError(f"Query blocked by validator: {reason}")

    db = get_sync_db()
    collection_name = query_dict["collection"]
    operation = query_dict["operation"].lower()
    collection = db[collection_name]

    results: Any = []

    if operation == "find":
        raw_filter = sanitize_filter(query_dict.get("filter", {}))
        projection = query_dict.get("projection", None)
        sort = query_dict.get("sort", None)
        limit = min(query_dict.get("limit", MAX_RESULTS), MAX_RESULTS)
        cursor = collection.find(raw_filter, projection)
        if sort:
            cursor = cursor.sort(list(sort.items()))
        cursor = cursor.limit(limit)
        results = list(cursor)

    elif operation == "count":
        raw_filter = sanitize_filter(query_dict.get("filter", {}))
        count = collection.count_documents(raw_filter)
        results = [{"count": count}]

    elif operation == "aggregate":
        pipeline = query_dict.get("pipeline", [])
        results = list(collection.aggregate(pipeline))

    # Deep-convert all BSON types (ObjectId, Decimal128, datetime) so
    # Pydantic can serialize the response without errors.
    return [_sanitize_doc(doc) for doc in results]
