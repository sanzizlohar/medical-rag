import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
TOP_K = int(os.getenv("TOP_K", "4"))
MAX_PAGES = int(os.getenv("MAX_PAGES", "500"))
MAX_CHUNKS = int(os.getenv("MAX_CHUNKS", "5000"))

# OCR for scanned/image-only pages (RapidOCR, runs locally on CPU)
OCR_ENABLED = os.getenv("OCR_ENABLED", "true").lower() == "true"
OCR_DPI = int(os.getenv("OCR_DPI", "150"))          # render resolution for OCR
OCR_MIN_CHARS = int(os.getenv("OCR_MIN_CHARS", "20"))  # pages with less text than this get OCR'd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
INDEX_DIR = os.path.join(BASE_DIR, "faiss_indexes")
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(INDEX_DIR, exist_ok=True)

# Frontend origins allowed to call this API (comma-separated; extend when deploying)
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
