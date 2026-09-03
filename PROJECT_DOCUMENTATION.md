# MedDoc Q&A — Complete Project Documentation

A full-stack **Retrieval-Augmented Generation (RAG)** system for medical documents.
Users upload medical PDFs and ask questions in a chat interface; the system retrieves
the most relevant passages via **semantic vector search** and Google Gemini answers
**strictly from those passages**, with **page-level citations** and a medical disclaimer.

---

## 1. System architecture

```
┌────────────────────────────── FRONTEND (React 18 + Vite, port 5173) ─────────────────────────────┐
│  ┌───────────────────┐  ┌──────────────────────────────────────────────────────┐                  │
│  │ DocumentPanel     │  │ Chat panel (App.jsx)                                 │                  │
│  │ - drag&drop/click │  │ - message bubbles (user/assistant)                   │                  │
│  │   PDF upload      │  │ - typing indicator while waiting                     │                  │
│  │ - doc list w/     │  │ - react-markdown rendering of answers                │                  │
│  │   pages/chunks    │  │ - expandable "Sources" panel per answer              │                  │
│  │ - delete button   │  │ - input box + Send                                   │                  │
│  └────────┬──────────┘  └──────────────────────────────────────────────────────┘                  │
└───────────┼───────────────────────────────────────────────────────────────────────────────────────┘
            │  fetch() calls to /api/*  (Vite dev proxy → http://localhost:8000)
┌───────────▼────────────────────── BACKEND (FastAPI, port 8000) ──────────────────────────────────┐
│  main.py   routes: /api/health · /api/upload · /api/chat · /api/documents · /api/documents/{id}  │
│            CORS for http://localhost:5173 · PDF-only + 25 MB validation                          │
│  ingest.py PDF → per-page text → chunks → Gemini embeddings → FAISS index (per document)         │
│  rag_chain.py retrieve top-4 chunks → prompt template → Gemini → grounded answer + sources       │
│  config.py reads .env (API key, model names, chunk sizes, paths)                                 │
│  schemas.py Pydantic request/response models                                                     │
└───────────┬──────────────────────────────────────────────────────────────────────────────────────┘
            │ HTTPS
┌───────────▼──────────────────────── GOOGLE GEMINI APIs ──────────────────────────────────────────┐
│  models/gemini-embedding-001  — text → 3072-dim vectors (used at upload AND query time)          │
│  gemini-3.6-flash             — grounded answer generation (temperature 0.2)                     │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
            │
┌───────────▼──────────────────────── DISK PERSISTENCE ────────────────────────────────────────────┐
│  backend/uploads/<id>_<name>.pdf          — original uploaded files                              │
│  backend/faiss_indexes/<doc_id>/          — one FAISS index per document (index.faiss + .pkl)    │
│  backend/faiss_indexes/documents.json     — manifest: filename, pages, chunks, uploaded_at       │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Project structure (every file explained)

```
medical-rag/
├── README.md                        # setup + usage guide
├── PROJECT_DOCUMENTATION.md         # this file
│
├── backend/
│   ├── requirements.txt             # pinned Python dependencies
│   ├── .env                         # GOOGLE_API_KEY + model config (gitignored)
│   ├── .env.example                 # template with placeholder key
│   ├── .gitignore                   # .env, uploads/, faiss_indexes/, __pycache__
│   ├── server.log                   # uvicorn output (dev)
│   ├── app/
│   │   ├── __init__.py              # makes `app` a Python package
│   │   ├── config.py                # env/settings loader
│   │   ├── schemas.py               # Pydantic request/response models
│   │   ├── ingest.py                # PDF → pages (OCR fallback) → chunks → FAISS
│   │   ├── rag_chain.py             # retrieval + grounded generation
│   │   └── main.py                  # FastAPI app + all routes
│   ├── sample_data/
│   │   ├── make_sample_pdf.py       # generates the 3-page sample PDF (PyMuPDF)
│   │   └── medical_fact_sheets.pdf  # dengue / hypertension / type-2 diabetes
│   ├── uploads/                     # stored PDFs (one per upload, id-prefixed)
│   └── faiss_indexes/               # vector indexes + documents.json manifest
│
└── frontend/
    ├── package.json                 # react, react-dom, react-markdown; vite dev deps
    ├── vite.config.js               # react plugin; proxies /api → localhost:8000
    ├── index.html                   # single-page shell (🩺 favicon)
    ├── .gitignore                   # node_modules/, dist/
    ├── browser_test.py              # Playwright end-to-end test
    ├── screenshots/                 # captured test screenshots
    └── src/
        ├── main.jsx                 # React root
        ├── App.jsx                  # chat panel, message state, /api/chat calls
        ├── index.css                # full medical theme (teal design system)
        └── components/
            └── DocumentPanel.jsx    # upload dropzone + document list + delete
```

### Backend modules in detail

#### `app/config.py`
Central configuration. Loads `.env` via python-dotenv and exposes:
- `GOOGLE_API_KEY` — Gemini API key
- `GEMINI_MODEL` (default `gemini-3.6-flash`) — generation model
- `EMBEDDING_MODEL` (default `models/gemini-embedding-001`) — embedding model
- `CHUNK_SIZE=1000`, `CHUNK_OVERLAP=150`, `TOP_K=4` — RAG tuning knobs
- `UPLOADS_DIR`, `INDEX_DIR` — created on startup if missing
- `MAX_UPLOAD_BYTES` = 25 MB

Model names live in config, **not code**, so a provider model change is a one-line edit.

#### `app/schemas.py` (Pydantic models)
- `UploadResponse {document_id, filename, pages, chunks}`
- `ChatRequest {question: 1..2000 chars}` / `ChatResponse {answer, sources[]}`
- `SourceChunk {document_id, document_name, page, text}`
- `DocumentInfo {document_id, filename, pages, chunks, uploaded_at}`
- `DeleteResponse {deleted, document_id}`

These validate incoming requests *and* guarantee the exact JSON shape sent to the UI
(undeclared fields are stripped — this is why `pages` must be declared here).

#### `app/ingest.py` — the ingestion pipeline
| Function | What it does |
|---|---|
| `extract_pages(pdf_path)` | Opens the PDF with PyMuPDF (`fitz`), returns list of per-page text |
| `ingest_pdf(pdf_path, filename)` | Orchestrates: new 12-hex `document_id` → extract pages → strip empty → `RecursiveCharacterTextSplitter` (1000/150, separators `\n\n`, `\n`, `". "`, `" "`, `""`) → each chunk becomes a LangChain `Document` with metadata `{document_id, document_name, page}` → `FAISS.from_documents` embeds + builds the index → `index.save_local(faiss_indexes/<id>/)` → manifest updated in `documents.json`. Raises `ValueError` if a PDF has zero extractable text (scanned image) |
| `search_all(question, k)` | Loads every document's FAISS index, runs `similarity_search_with_score(question, k)` on each, merges all candidates, sorts by L2 distance (lower = more similar), returns top-k overall |
| `list_documents()` / `delete_document(id)` | Read/modify the JSON manifest; delete also `shutil.rmtree`s the index folder |

Design note: **one FAISS index per document** makes deletion trivial and total
(filesystem folder removal) instead of vector-store-filter deletes.

#### `app/rag_chain.py` — the query pipeline
1. `ingest.search_all(question, TOP_K)` → top-4 chunks across all documents
2. Deduplicate identical (doc, page, text) hits
3. Build context blocks: `[Source: <name>, page N]\n<chunk text>` joined by `---`
4. System prompt rules: answer only from context → exact refusal sentence if missing →
   never invent doses/diagnoses → bullet formatting when appropriate → cite as
   `[Document Name, page N]` → always end with the ⚠️ consult-a-professional disclaimer
5. `ChatPromptTemplate` (system + human) piped into `ChatGoogleGenerativeAI`
   (`gemini-3.6-flash`, temperature **0.2**)
6. Returns `{"answer": str, "sources": [SourceChunk...]}` — the same chunks given to
   the model, so the UI's Sources panel shows exactly what the answer was grounded in

If no documents exist, returns a friendly "upload a PDF first" message without
calling the LLM.

#### `app/main.py` — FastAPI app
- CORS middleware allowing the Vite dev origin (`localhost:5173`)
- Routes (full reference in §4)
- Upload validation: extension must be `.pdf`; size ≤ 25 MB; on ingestion failure the
  stored file is deleted and a 422/500 with the reason is returned

### Frontend files in detail

#### `src/App.jsx`
- Holds `messages` state: `{role: 'user'|'assistant', text, sources[]}`
- `ask()` — POSTs `/api/chat`, appends the user bubble immediately, shows the typing
  indicator, appends the answer with sources, and renders errors as assistant bubbles
- `<Sources>` component — collapsible "📄 Sources (N)" section; each entry shows
  document name + page + a 300-char text preview
- Auto-scrolls to the newest message

#### `src/components/DocumentPanel.jsx`
- Dropzone with drag-over highlight; file input fallback; client-side PDF check
- `upload()` — FormData POST to `/api/upload`; shows ingest status (spinner →
  success "X pages, Y chunks indexed" / error)
- Lists documents with pages/chunks stats and a ✕ delete button (DELETE + optimistic
  UI update)
- Refreshes whenever a new upload completes (`refreshSignal` prop)

#### `src/index.css`
Complete custom design system in CSS variables (teal medical palette `#1a7f6e`,
light background, 12px radii). Covers header gradient, dropzone dashed border +
drag-over state, spinner keyframes, chat bubbles (user = filled teal right-aligned,
assistant = white card left-aligned), blinking typing dots, sources cards, responsive
breakpoint at 768px (sidebar stacks above chat).

#### `vite.config.js`
Dev server on 5173 with `proxy: {'/api': 'http://localhost:8000'}` — the frontend
code calls relative `/api/...` paths, so there are no hardcoded URLs and no CORS
issues in dev.

---

## 3. The RAG pipeline step by step (with real numbers)

**Ingestion** (measured with the 3-page sample PDF):
1. PyMuPDF extracts 3 pages of text
2. Splitter produces **5 chunks** (some pages split, empties skipped)
3. Each chunk → Gemini embedding → 3072-dimension float vector
4. FAISS index built (exact L2 search) and saved to disk with the manifest entry

**Query** (e.g. *"What are the warning signs of severe dengue?"*):
1. Question → same embedding model → vector
2. FAISS searched per document; top-4 chunks merged by distance
3. For the sample PDF the top hit was the dengue page-1 chunk (distance ≈ 0.44)
4. Prompt = system rules + 4 labeled context blocks + question → Gemini
5. Gemini returns bulleted answer citing `[medical_fact_sheets.pdf, page 1]` and the
   required disclaimer; response also carries the 4 source chunks for the UI

---

## 4. API reference

Base URL: `http://localhost:8000` (dev docs UI at `/docs`)

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/api/health` | — | `{status, api_key_configured, model}` |
| POST | `/api/upload` | multipart form field `file` (PDF ≤ 25 MB) | `UploadResponse` |
| POST | `/api/chat` | `{"question": "..."}` | `ChatResponse` |
| GET | `/api/documents` | — | `{documents: DocumentInfo[]}` |
| DELETE | `/api/documents/{document_id}` | — | `DeleteResponse` |

**curl examples:**

```bash
# upload
curl -X POST -F "file=@medical_fact_sheets.pdf" http://localhost:8000/api/upload
# → {"document_id":"6df98a0102cd","filename":"medical_fact_sheets.pdf","pages":3,"chunks":5}

# chat
curl -X POST -H "Content-Type: application/json" \
     -d '{"question":"What are the warning signs of severe dengue?"}' \
     http://localhost:8000/api/chat
# → {"answer":"...bulleted answer... [medical_fact_sheets.pdf, page 1]... ⚠️ ...",
#    "sources":[{"document_id":"...","document_name":"medical_fact_sheets.pdf","page":1,"text":"..."}]}

# list / delete
curl http://localhost:8000/api/documents
curl -X DELETE http://localhost:8000/api/documents/6df98a0102cd
```

**Error responses** (all structured JSON `{"detail": "..."}`):
- 400 non-PDF upload or invalid file name · 413 > 25 MB
- 422 no extractable text (scanned PDF), page limit exceeded (> `MAX_PAGES`), or
  chunk limit exceeded (> `MAX_CHUNKS`)
- 404 unknown document id · 500 missing API key / LLM or ingestion failure

---

## 5. Configuration reference (backend/.env)

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` | — (required) | Gemini API key from aistudio.google.com/apikey |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Generation model |
| `EMBEDDING_MODEL` | `models/gemini-embedding-001` | Embedding model |
| `CHUNK_SIZE` | `1000` | Chunk character size |
| `CHUNK_OVERLAP` | `150` | Chunk overlap |
| `TOP_K` | `4` | Chunks retrieved per question |
| `MAX_PAGES` | `500` | Hard page limit per uploaded PDF (422 rejection above it) |
| `MAX_CHUNKS` | `5000` | Hard chunk limit per uploaded PDF (422 rejection above it) |
| `OCR_ENABLED` | `true` | OCR fallback for scanned/image-only pages (RapidOCR, local CPU) |
| `OCR_DPI` | `150` | Render resolution used when OCR-ing a page (higher = slower, more accurate) |
| `OCR_MIN_CHARS` | `20` | Pages whose text layer is shorter than this get OCR'd |

---

## 6. Running the project

```bash
# Backend
cd backend
pip install -r requirements.txt          # Python 3.10+
# put your key in .env (see .env.example)
python -m uvicorn app.main:app --port 8000

# Frontend (second terminal)
cd frontend
npm install                              # Node 18+
npm run dev                              # open http://localhost:5173
```

Sample data: `python sample_data/make_sample_pdf.py` regenerates
`sample_data/medical_fact_sheets.pdf`.

---

## 7. Testing & verification performed

1. **Unit-level script tests** — import checks for every dependency; direct pipeline
   runs (extract → ingest → search) verifying chunk counts and hit relevance
2. **API tests (curl)** — health, upload (success + non-PDF rejection + oversize),
   chat (grounded answer with correct page citations), list, delete, error paths
3. **Grounding/refusal check** — question answerable from docs → cited answer;
   the prompt enforces the "I could not find this information…" fallback otherwise
4. **End-to-end Playwright browser test** (`frontend/browser_test.py`) — launches
   headless Chromium, loads the real UI, verifies header + document list, sends a
   real question through the form, waits for the typing indicator to clear, asserts
   the grounded answer (checks for "HbA1c"/"126"), expands the Sources panel and
   verifies document+page entries. Screenshots saved to `frontend/screenshots/`
5. **Visual review** — screenshots inspected for layout, sidebar stats, bubble
   styling (caught and fixed the missing `pages` field this way)

---

## 8. Known issues encountered & resolutions (engineering log)

| Issue | Root cause | Fix |
|---|---|---|
| Process segfault (exit 139) during upload | ChromaDB 1.5.x Rust storage layer access-violation on Windows (`rust.py _upsert`), isolated via `faulthandler` | Migrated vector store to **FAISS**; per-document index design (also simpler deletes) |
| `404 models/text-embedding-004 is not found` | Newer API keys don't support the legacy embedding model | Queried `ListModels`; switched to `gemini-embedding-001`; model names moved to config |
| `404 gemini-2.0-flash is no longer available` | Model retired by the provider | Switched to `gemini-3.6-flash` via `.env` (no code change) |
| pip dependency conflicts (`langchain-core` 1.x pulled in) | Unpinned `langchain-community` upgrade | Pinned `langchain-community==0.3.14`, `langchain-core<0.4`, removed `langchain-classic`; verified with `pip check` |
| Sidebar showed "pages · 5 chunks" without a number | `DocumentInfo` Pydantic model didn't declare `pages`, so it was stripped from responses | Added `pages: int` to the schema |

---

## 9. Security & privacy notes

- The API key lives in `backend/.env`, which is **gitignored**; `.env.example` is the
  committed template. Never commit real keys.
- Medical-domain guardrails are prompt-level and product-level (citations,
  disclaimer, refusal) — the system provides *information from uploaded documents*,
  not diagnoses, and says so on every answer.
- Uploaded PDFs and vector indexes stay on the local disk; the only external calls
  are to Google's Gemini APIs (text + embeddings). For real patient-level data, use
  local open-source models, add auth + encryption at rest, and follow applicable
  regulations (HIPAA/GDPR) — see roadmap.
- Inputs are constrained: PDF-only, 25 MB cap, **500-page / 5,000-chunk limits**
  (configurable via `MAX_PAGES` / `MAX_CHUNKS`), question length 1–2000 chars,
  filename path-traversal protected (`basename` + backslash normalization + empty-name
  guard).
- Concurrency: FastAPI serves sync endpoints in a thread pool, so all manifest
  read-modify-write operations are protected by a `threading.Lock` (safe concurrent
  uploads/deletes).

## 10. Performance characteristics & limits

- Ingestion is bounded by embedding API latency (~seconds for typical PDFs)
- Retrieval is in-process FAISS (exact L2) — milliseconds for small/medium libraries;
  `search_all` loads each document's index per query (fine for tens of documents;
  add caching or a merged index for hundreds+)
- Known limits: OCR adds ~5–15 s per scanned page (RapidOCR on CPU; engine init is lazy
  and inference is serialized with a lock because the engine is not thread-safe) ·
  no user auth · no conversation memory · retrieval scans all documents (add
  per-document filters at scale)

## 11. Roadmap

1. OCR (Tesseract) for scanned documents — **done: RapidOCR ships with the app** · 2. Token streaming responses ·
3. Multi-turn conversation memory · 4. Hybrid retrieval (BM25 + vectors) for exact
terms like drug names · 5. Cross-encoder re-ranking · 6. RAGAS-style evaluation
(faithfulness, context precision) · 7. Docker + cloud deploy + auth + multi-user ·
8. Local-model mode (Ollama) for privacy-critical use
