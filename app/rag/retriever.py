"""
retriever.py

Manages the ChromaDB vector store:
  - add_documents : embed and store document chunks
  - get_retriever : return a LangChain retriever for similarity search
  - answer_with_rag: run a full RAG query against stored documents
"""

import os
import logging
from typing import List

import chromadb
from chromadb.config import Settings
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_chroma import Chroma              # dedicated package in 0.3.x
from langchain_google_genai import ChatGoogleGenerativeAI

from app.rag.embeddings import get_embeddings
from app.prompts.mongo_prompts import RAG_ANSWER_PROMPT

logger = logging.getLogger(__name__)

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
COLLECTION_NAME = "roadaid_docs"
TOP_K = 2      # Number of relevant chunks to retrieve

# Disable ChromaDB's anonymous telemetry — stops the posthog errors in logs
_CHROMA_SETTINGS = Settings(anonymized_telemetry=False)


def _get_vector_store() -> Chroma:
    """Load or create the ChromaDB vector store (telemetry disabled)."""
    client = chromadb.PersistentClient(
        path=CHROMA_PERSIST_DIR,
        settings=_CHROMA_SETTINGS,
    )
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        client=client,          # pass explicit client so settings are honoured
    )


def add_documents(chunks: List[Document]) -> int:
    """
    Embed and store document chunks in ChromaDB.
    Returns the number of chunks added.
    """
    vector_store = _get_vector_store()
    vector_store.add_documents(chunks)
    # langchain-chroma auto-persists via PersistentClient — no .persist() call needed
    logger.info("Added %d chunks to ChromaDB", len(chunks))
    return len(chunks)


def get_retriever():
    """Return a LangChain retriever backed by ChromaDB."""
    vector_store = _get_vector_store()
    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": TOP_K},
    )


def answer_with_rag(question: str) -> dict:
    """
    Retrieve relevant document chunks and ask Gemini 2.5 Pro
    to answer the question based on that context.

    Returns:
        {
            "answer": str,
            "source_documents": list of metadata dicts
        }
    """
    retriever = get_retriever()
    relevant_docs = retriever.invoke(question)

    if not relevant_docs:
        return {
            "answer": "No relevant documents found for your question.",
            "source_documents": [],
        }

    # Build context string from retrieved chunks
    context = "\n\n---\n\n".join(doc.page_content for doc in relevant_docs)

    # Ask Gemini to answer using context
    llm = ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-pro"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.2,
        # convert_system_message_to_human removed in langchain-google-genai 2.x
        # Gemini 2.5 Pro natively supports system messages
    )
    print("context: ", context)
    prompt_text = RAG_ANSWER_PROMPT.format(context=context, question=question)
    response = llm.invoke([HumanMessage(content=prompt_text)])

    sources = [
        {"source": doc.metadata.get("source", "unknown"), "page": doc.metadata.get("page", 0)}
        for doc in relevant_docs
    ]

    return {
        "answer": response.content.strip(),
        "source_documents": sources,
    }
