import { useEffect, useRef, useState } from 'react'

// In dev, Vite proxies /api to localhost:8000. In production, set VITE_API_URL
// (e.g. https://your-backend.onrender.com/api) at build time.
const API = import.meta.env.VITE_API_URL || '/api'

export default function DocumentPanel({ refreshSignal, onUploaded }) {
  const [documents, setDocuments] = useState([])
  const [uploading, setUploading] = useState(false)
  const [status, setStatus] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef(null)

  useEffect(() => {
    fetch(`${API}/documents`)
      .then((r) => r.json())
      .then((d) => setDocuments(d.documents || []))
      .catch(() => {})
  }, [refreshSignal])

  async function upload(file) {
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setStatus({ kind: 'error', text: '✗ only .pdf files are accepted' })
      return
    }
    setUploading(true)
    setStatus({ kind: 'info', text: `ingesting "${file.name}" … embedding pages, one moment (scanned PDFs take longer — OCR runs locally)` })
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API}/upload`, { method: 'POST', body: form })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Upload failed')
      setStatus({
        kind: 'success',
        text: `✓ ${data.filename} — ${data.pages} pages` +
          (data.ocr_pages ? ` (${data.ocr_pages} via OCR)` : '') +
          ` · ${data.chunks} chunks indexed. Ready to query.`,
      })
      onUploaded()
    } catch (err) {
      setStatus({ kind: 'error', text: `✗ ${err.message}` })
    } finally {
      setUploading(false)
    }
  }

  async function remove(docId) {
    const res = await fetch(`${API}/documents/${docId}`, { method: 'DELETE' })
    if (!res.ok) {
      setStatus({ kind: 'error', text: '✗ could not delete the document — try again' })
      return
    }
    setDocuments((docs) => docs.filter((d) => d.document_id !== docId))
  }

  return (
    <aside className="doc-panel">
      <h2 className="panel-title">Documents ({documents.length})</h2>

      <div
        className={`dropzone ${dragOver ? 'drag-over' : ''} ${uploading ? 'busy' : ''}`}
        onClick={() => !uploading && fileInputRef.current.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          if (!uploading) upload(e.dataTransfer.files[0])
        }}
      >
        {uploading ? (
          <>
            <span className="spinner" />
            <strong>INDEXING…</strong>
            <span>embedding chunks</span>
          </>
        ) : (
          <>
            <span className="drop-icon">⬆</span>
            <strong>UPLOAD PDF</strong>
            <span>click or drag &amp; drop · max 500 pages</span>
            <span>scanned PDFs are welcome (auto-OCR)</span>
          </>
        )}
      </div>
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        hidden
        onChange={(e) => {
          upload(e.target.files[0])
          e.target.value = ''
        }}
      />

      {status && <div className={`status ${status.kind}`}>{status.text}</div>}

      <ul className="doc-list">
        {documents.length === 0 && (
          <li className="empty">no documents yet — upload a PDF to start</li>
        )}
        {documents.map((doc) => (
          <li key={doc.document_id}>
            <div className="doc-info">
              <strong title={doc.filename}>📕 {doc.filename}</strong>
              <span>p.1–{doc.pages} · {doc.chunks} chunks{doc.ocr_pages ? ` · ${doc.ocr_pages} OCR` : ''}</span>
            </div>
            <button className="delete" title="Delete document" onClick={() => remove(doc.document_id)}>
              ✕
            </button>
          </li>
        ))}
      </ul>
    </aside>
  )
}
