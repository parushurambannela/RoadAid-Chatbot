"""
schema_loader.py

Single source of truth for all collection schemas.
Reads roadaid_collection_metadata.csv and builds prompt-ready schema
descriptions for Gemini, replacing the old hardcoded string approach.

Why CSV instead of hardcoded strings:
  - 122 real collections with actual field names, types, and sample values
  - Sample values let the LLM generate accurate filters (e.g. status="active")
  - One place to update when the database schema changes
  - No code change needed to add/rename a collection

Keyword Routing (get_schemas_for_question):
  Instead of sending all 122 schemas (~16K tokens) with every prompt, we score
  each collection against the question using keyword overlap and return only the
  top N most relevant ones (~500-800 tokens).

  Scoring weights:
    collection name match  → 10 pts  (strongest signal)
    full_form word match   →  7 pts
    key_fields match       →  5 pts
    category word match    →  3 pts
    description word match →  2 pts  (weakest — too many common words)

Usage:
    from app.schemas.schema_loader import get_schemas_for_question, get_collection_names
"""

import ast
import csv
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Resolve CSV path relative to project root.
# Override with METADATA_CSV_PATH env var if the file lives elsewhere.
_CSV_PATH = Path(os.getenv("METADATA_CSV_PATH", "roadaid_collection_metadata.csv"))

# Internal metadata fields added by Mongoose — not useful for query generation
_SKIP_FIELDS = {"__v", "_id", "createdAt", "updatedAt", "createdBy", "updatedBy"}


# ── Parsing helpers ───────────────────────────────────────────────────────────

def _parse_blueprint(raw: str) -> dict:
    """
    Parse the 'blueprint' column which is stored as a Python dict literal.
    Returns an empty dict if parsing fails.
    """
    if not raw or not raw.strip():
        return {}
    try:
        return ast.literal_eval(raw.strip())
    except Exception:
        logger.debug("Could not parse blueprint (truncated): %s", raw[:80])
        return {}


def _extract_key_field_samples(blueprint: dict, key_fields_str: str) -> str:
    """
    Build a compact sample-values string for the key fields only.

    Example output:
        status: active, inactive, on_leave | severity: Fatal, Minor Injured
    """
    if not blueprint or not key_fields_str:
        return ""

    key_fields = [f.strip() for f in key_fields_str.split(",") if f.strip()]
    parts = []

    for field in key_fields:
        meta = blueprint.get(field, {})
        samples = [str(s) for s in meta.get("sample_values", []) if str(s).strip()]
        if samples:
            parts.append(f"{field}: {', '.join(samples[:5])}")

    return " | ".join(parts)


# ── Core loader ───────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def load_all_schemas() -> list[dict]:
    """
    Load every row from the metadata CSV.
    Result is cached after the first call — restart the server to reload.
    Each row gets an extra '_blueprint' key holding the parsed blueprint dict.
    """
    if not _CSV_PATH.exists():
        logger.error(
            "Metadata CSV not found at '%s'. "
            "Schema context will be empty — set METADATA_CSV_PATH in .env",
            _CSV_PATH,
        )
        return []

    schemas = []
    with open(_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["_blueprint"] = _parse_blueprint(row.get("blueprint", ""))
            schemas.append(row)

    logger.info("Loaded %d collection schemas from %s", len(schemas), _CSV_PATH.name)
    return schemas


# ── Text builders ─────────────────────────────────────────────────────────────

def build_collection_schema_text(row: dict) -> str:
    """
    Convert one CSV row into a compact, LLM-readable schema block.

    Example output:
        Collection: drivers (Drivers) [Safety & Accidents]
          Description: Stores driver information including assignments...
          Key Fields: name, vehicleNumber, status, assignedRoad, licenseType
          Sample Values: status: active, inactive | assignedRoad: NH44, SH-12
    """
    blueprint       = row.get("_blueprint", {})
    key_fields_str  = row.get("key_fields", "")
    description     = row.get("collection_description", "")
    collection_name = row["Collection_name"]
    full_form       = row.get("full_form", "")
    category        = row.get("collection_category", "")

    # Keep descriptions short so the prompt doesn't balloon
    if len(description) > 160:
        description = description[:157] + "..."

    sample_values = _extract_key_field_samples(blueprint, key_fields_str)
    sample_line   = f"\n  Sample Values: {sample_values}" if sample_values else ""

    return (
        f"Collection: {collection_name} ({full_form}) [{category}]\n"
        f"  Description: {description}\n"
        f"  Key Fields: {key_fields_str}"
        f"{sample_line}"
    )


def get_all_schemas_text() -> str:
    """
    Return ALL 122 schemas as a single string.
    Only used for debugging / inspection — NOT sent to the prompt at runtime.
    Use get_schemas_for_question() for prompts instead.
    """
    schemas = load_all_schemas()
    if not schemas:
        return "No collection schema information available."
    parts = [build_collection_schema_text(row) for row in schemas]
    return "\n\n".join(parts)


# ── Utility helpers ───────────────────────────────────────────────────────────

def get_collection_names() -> set[str]:
    """
    Return the complete set of valid collection names.
    Used by the query validator to block queries against unknown collections.
    """
    return {row["Collection_name"] for row in load_all_schemas()}


def get_schema_for_collection(collection_name: str) -> Optional[dict]:
    """Look up a single collection by name. Returns None if not found."""
    for row in load_all_schemas():
        if row["Collection_name"] == collection_name:
            return row
    return None


def get_schema_summary() -> list[dict]:
    """
    Return a lightweight summary list — useful for debug/inspection endpoints.
    """
    return [
        {
            "collection": row["Collection_name"],
            "full_form": row.get("full_form", ""),
            "category": row.get("collection_category", ""),
            "key_fields": row.get("key_fields", ""),
        }
        for row in load_all_schemas()
    ]
