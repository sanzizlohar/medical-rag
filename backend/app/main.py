import os
import shutil
import uuid

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from . import config, ingest, rag_chain
from .schemas import (
    ChatRequest,
    ChatResponse,
    DeleteResponse,
    DocumentListResponse,
    UploadResponse,
)

app = FastAPI(
    title="Medical Document Q&A API",
    description="RAG system: upload medical PDFs and ask questions about them.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "api_key_configured": bool(config.GOOGLE_API_KEY),
        "model": config.GEMINI_MODEL,
    }


@app.post("/api/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    contents = await file.read()
    if len(contents) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 25 MB limit.")

    safe_name = os.path.basename(file.filename.replace("\\", "/")).strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid file name.")
    pdf_path = os.path.join(config.UPLOADS_DIR, f"{uuid.uuid4().hex[:12]}_{safe_name}")
    with open(pdf_path, "wb") as f:
        f.write(contents)

    try:
        summary = ingest.ingest_pdf(pdf_path, safe_name)
    except ValueError as exc:
        os.remove(pdf_path)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        os.remove(pdf_path)
        raise HTTPException(
            status_code=500, detail=f"Ingestion failed: {exc}"
        ) from exc
    return summary


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not config.GOOGLE_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_API_KEY is not configured. Set it in backend/.env",
        )
    try:
        result = rag_chain.answer_question(request.question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}") from exc
    return result


@app.get("/api/documents", response_model=DocumentListResponse)
def documents():
    return {"documents": ingest.list_documents()}


@app.delete("/api/documents/{document_id}", response_model=DeleteResponse)
def delete_document(document_id: str):
    deleted = ingest.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"deleted": True, "document_id": document_id}
