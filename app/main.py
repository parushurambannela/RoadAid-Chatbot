import logging
import os
from dotenv import load_dotenv

# Load .env FIRST — before any other app import reads os.getenv().
# override=True ensures .env always wins over any stale shell env vars.
load_dotenv(override=True)

# Silence ChromaDB's posthog telemetry before chromadb is imported anywhere.
# Must be set as an env var — the Settings() approach only works per-client,
# but the posthog event fires at the module level on first import.
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import chat, rag, auth
from app.database.mongo_client import connect_to_mongo, close_mongo_connection

# ── Logging setup ─────────────────────────────────────────────────────────────
# Strategy:
#   - Root logger  → INFO  (keeps third-party libraries quiet)
#   - app.*        → LOG_LEVEL from .env (default DEBUG — shows your debug logs)
#
# This means you'll see your logger.debug() calls without being flooded by
# LangChain / Google / httpx / ChromaDB internal debug messages.

_app_log_level = getattr(logging, os.getenv("LOG_LEVEL", "DEBUG").upper(), logging.DEBUG)

logging.basicConfig(
    level=logging.INFO,                     # third-party libraries: INFO and above only
    format="%(asctime)s  %(levelname)-8s  %(name)s  —  %(message)s",
    datefmt="%H:%M:%S",
)

# Set all app.* loggers to the level from .env
for _name in ("app.routes", "app.services", "app.schemas", "app.rag",
              "app.utils", "app.database", "app.prompts"):
    logging.getLogger(_name).setLevel(_app_log_level)

app = FastAPI(
    title="RoadAid AI Assistant",
    description="AI-powered assistant for querying the RoadAid MongoDB database using Gemini 2.5 Pro.",
    version="1.0.0",
)

# Allow all origins for local development — tighten this in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await connect_to_mongo()


@app.on_event("shutdown")
async def on_shutdown():
    await close_mongo_connection()


# Register route groups
app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(rag.router, prefix="/api/v1", tags=["RAG"])


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "RoadAid AI Assistant", "llm": "gemini-2.5-pro"}
