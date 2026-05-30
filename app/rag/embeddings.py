"""
embeddings.py

Creates and returns the Google Generative AI embeddings object
used for both indexing documents and querying ChromaDB.
"""

import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """
    Returns a GoogleGenerativeAIEmbeddings instance.
    Uses the embedding model defined in the GEMINI_EMBEDDING_MODEL env var.

    Run test_embeddings.py to find the exact model name your API key supports.

    task_type:
      - retrieval_document : used when indexing/storing chunks
      - retrieval_query    : used when querying (similarity search)
    Both use the same model; task_type hints the API for better quality.
    """
    return GoogleGenerativeAIEmbeddings(
        model=os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-2"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        task_type="retrieval_document",
    )
