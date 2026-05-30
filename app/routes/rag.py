import os
import shutil
import logging
from typing import Any

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel, Field

from app.rag.loader import load_and_split_pdf
from app.rag.retriever import add_documents, answer_with_rag

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = "./uploaded_docs"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class RAGQueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


class RAGQueryResponse(BaseModel):
    answer: str
    source_documents: list[Any]


class UploadResponse(BaseModel):
    message: str
    filename: str
    chunks_added: int


@router.post("/rag/upload", response_model=UploadResponse, summary="Upload a PDF document for RAG")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a PDF file. It will be split into chunks, embedded with
    Google Generative AI embeddings, and stored in ChromaDB.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    save_path = os.path.join(UPLOAD_DIR, file.filename)

    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        chunks = load_and_split_pdf(save_path)
        count = add_documents(chunks)

        logger.info("Uploaded and indexed %s (%d chunks)", file.filename, count)
        return UploadResponse(
            message="Document uploaded and indexed successfully.",
            filename=file.filename,
            chunks_added=count,
        )

    except Exception as exc:
        logger.error("Failed to process upload: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to process document: {exc}")


@router.post("/rag/query", response_model=RAGQueryResponse, summary="Ask a question over uploaded documents")
async def rag_query(request: RAGQueryRequest):
    """
    Ask a question answered from the uploaded PDF documents
    using RAG (Retrieval Augmented Generation) with Gemini 2.5 Pro.
    """
    try:
        result = answer_with_rag(request.question)
        return RAGQueryResponse(**result)
    except Exception as exc:
        logger.error("RAG query failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"RAG query failed: {exc}")
