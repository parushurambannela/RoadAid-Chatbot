"""
Query safety validator.

The LLM should only generate read operations, but this module
adds a second line of defence by rejecting anything destructive
before it reaches MongoDB.

ALLOWED_COLLECTIONS is now loaded dynamically from the metadata CSV
via schema_loader — no need to maintain a hardcoded list when collections change.
"""

from app.schemas.schema_loader import get_collection_names

BLOCKED_OPERATIONS = [
    "insert",
    "insertone",
    "insertmany",
    "update",
    "updateone",
    "updatemany",
    "replace",
    "replaceone",
    "delete",
    "deleteone",
    "deletemany",
    "drop",
    "dropcollection",
    "dropdatabase",
    "create_collection",
    "rename",
    "bulk_write",
]

ALLOWED_OPERATIONS = {"find", "count", "aggregate", "count_documents"}


def validate_query(parsed: dict) -> tuple[bool, str]:
    """
    Validate a parsed query dict before executing it.

    Returns:
        (True, "") if the query is safe.
        (False, reason) if the query should be blocked.
    """
    if not isinstance(parsed, dict):
        return False, "Query must be a dictionary."

    # Block error sentinel returned by LLM
    if "error" in parsed:
        return False, parsed["error"]

    operation  = parsed.get("operation", "").lower()
    collection = parsed.get("collection", "").lower()

    # Load allowed collections dynamically from the CSV (cached after first call)
    allowed_collections = get_collection_names()

    if collection not in allowed_collections:
        return False, (
            f"Unknown collection: '{collection}'. "
            f"Must be one of the {len(allowed_collections)} collections defined in the metadata CSV."
        )

    if operation not in ALLOWED_OPERATIONS:
        return False, f"Operation '{operation}' is not allowed. Only read operations are permitted."

    # Belt-and-suspenders: scan the full query string for blocked keywords
    query_str = str(parsed).lower()
    for blocked in BLOCKED_OPERATIONS:
        if blocked in query_str:
            return False, f"Query contains blocked keyword: '{blocked}'."

    return True, ""


def sanitize_filter(filter_dict: dict) -> dict:
    """
    Remove any keys that could be dangerous operators.
    Currently a light check — extend as needed.
    """
    if not isinstance(filter_dict, dict):
        return {}

    dangerous_top_level_keys = {"$where", "$function", "$accumulator"}
    return {k: v for k, v in filter_dict.items() if k not in dangerous_top_level_keys}
