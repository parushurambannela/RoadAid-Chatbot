"""
loader.py

Loads PDF documents, splits them into chunks, and returns
LangChain Document objects ready for embedding.
"""

import os
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter  # moved to own package in 0.3.x
from langchain_core.documents import Document


CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", 1000))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", 150))


def load_pdf(file_path: str) -> List[Document]:
    """Load a PDF from disk and return raw LangChain Document pages."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF not found: {file_path}")

    loader = PyPDFLoader(file_path)
    pages = loader.load()
    return pages


def split_documents(documents: List[Document]) -> List[Document]:
    """
    Split documents into smaller chunks for embedding.
    Overlap helps preserve context at chunk boundaries.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    return splitter.split_documents(documents)


def load_and_split_pdf(file_path: str) -> List[Document]:
    """Convenience function: load a PDF and return split chunks."""
    pages = load_pdf(file_path)
    chunks = split_documents(pages)
    return chunks
