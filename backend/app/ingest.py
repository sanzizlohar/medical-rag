"""PDF ingestion: parse pages -> chunk -> embed -> store in per-document FAISS index."""

import json
import os
import shutil
import threading
import uuid
from datetime import datetime, timezone

import fitz  # PyMuPDF
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

from . import config

MANIFEST_PATH = os.path.join(config.INDEX_DIR, "documents.json")
_manifest_lock = threading.Lock()

# --- OCR (scanned pages) ---
_ocr_engine = None
_ocr_lock = threading.Lock()


def _get_ocr_engine():
    """Lazy-load the RapidOCR engine (bundled ONNX models, local CPU)."""
    global _ocr_engine
    if _ocr_engine is None:
        with _ocr_lock:
            if _ocr_engine is None:
                from rapidocr_onnxruntime import RapidOCR
                _ocr_engine = RapidOCR()
    return _ocr_engine


def _ocr_page(page) -> str:
    """Render one PDF page to an image and OCR it (serialized: the engine is not thread-safe)."""
    import cv2
    import numpy as np

    pix = page.get_pixmap(dpi=config.OCR_DPI)
    img = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)
    engine = _get_ocr_engine()
    with _ocr_lock:
        result, _ = engine(img)
    if not result:
        return ""
    return "\n".join(item[1] for item in result)


def _embeddings() -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(
        model=config.EMBEDDING_MODEL, google_api_key=config.GOOGLE_API_KEY
    )


def _index_dir(document_id: str) -> str:
    return os.path.join(config.INDEX_DIR, document_id)


def _load_manifest() -> dict:
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_manifest(manifest: dict) -> None:
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def _load_index(document_id: str) -> FAISS | None:
    path = _index_dir(document_id)
    if not os.path.exists(os.path.join(path, "index.faiss")):
        return None
    return FAISS.load_local(
        path, _embeddings(), allow_dangerous_deserialization=True
    )


def extract_pages(pdf_path: str) -> tuple[list[str], int]:
    """Return (per-page texts, number of pages that required OCR).
    Pages with (almost) no text layer are treated as scanned and OCR'd."""
    pages: list[str] = []
    ocr_pages = 0
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text = page.get_text("text").strip()
            if len(text) < config.OCR_MIN_CHARS and config.OCR_ENABLED:
                ocr_text = _ocr_page(page).strip()
                if ocr_text:
                    text = ocr_text
                    ocr_pages += 1
            pages.append(text)
    return pages, ocr_pages


def ingest_pdf(pdf_path: str, original_filename: str) -> dict:
    """Parse, chunk, embed, and index a PDF. Returns document summary."""
    document_id = uuid.uuid4().hex[:12]
    pages, ocr_pages = extract_pages(pdf_path)

    if len(pages) > config.MAX_PAGES:
        raise ValueError(
            f"This PDF has {len(pages)} pages, but the limit is {config.MAX_PAGES}. "
            "Split it into parts or raise MAX_PAGES in backend/.env."
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    docs: list[Document] = []
    for page_num, page_text in enumerate(pages, start=1):
        text = page_text.strip()
        if not text:
            continue
        for chunk in splitter.split_text(text):
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "document_id": document_id,
                        "document_name": original_filename,
                        "page": page_num,
                    },
                )
            )

    if not docs:
        raise ValueError(
            "No readable text found in this PDF (even OCR came up empty - "
            "the scan may be blank or too low quality)."
        )
    if len(docs) > config.MAX_CHUNKS:
        raise ValueError(
            f"This PDF produced {len(docs)} chunks, but the limit is {config.MAX_CHUNKS}. "
            "Remove it, then raise MAX_CHUNKS in backend/.env or lower CHUNK_SIZE."
        )

    index = FAISS.from_documents(docs, _embeddings())
    index.save_local(_index_dir(document_id))

    with _manifest_lock:
        manifest = _load_manifest()
        manifest[document_id] = {
            "filename": original_filename,
            "pdf_file": os.path.basename(pdf_path),
            "pages": len(pages),
            "ocr_pages": ocr_pages,
            "chunks": len(docs),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_manifest(manifest)

    return {
        "document_id": document_id,
        "filename": original_filename,
        "pages": len(pages),
        "ocr_pages": ocr_pages,
        "chunks": len(docs),
    }


def list_documents() -> list[dict]:
    manifest = _load_manifest()
    return [
        {"document_id": doc_id, **info} for doc_id, info in manifest.items()
    ]


def search_all(question: str, k: int) -> list[tuple[Document, float]]:
    """Search every ingested document's index; return top-k (doc, distance),
    sorted best-first (smallest L2 distance)."""
    candidates: list[tuple[Document, float]] = []
    for document_id in _load_manifest():
        index = _load_index(document_id)
        if index is not None:
            candidates.extend(index.similarity_search_with_score(question, k=k))
    candidates.sort(key=lambda pair: pair[1])
    return candidates[:k]


def delete_document(document_id: str) -> bool:
    with _manifest_lock:
        manifest = _load_manifest()
        if document_id not in manifest:
            return False
        info = manifest.pop(document_id)
        _save_manifest(manifest)
    shutil.rmtree(_index_dir(document_id), ignore_errors=True)
    pdf_file = info.get("pdf_file")
    if pdf_file:
        try:
            os.remove(os.path.join(config.UPLOADS_DIR, pdf_file))
        except FileNotFoundError:
            pass
    return True
