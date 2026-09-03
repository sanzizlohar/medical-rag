import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import DocumentPanel from './components/DocumentPanel.jsx'

// In dev, Vite proxies /api to localhost:8000. In production, set VITE_API_URL
// (e.g. https://your-backend.onrender.com/api) at build time.
const API = import.meta.env.VITE_API_URL || '/api'

export default function App() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text:
        '**Ask anything.** Upload a medical PDF in the panel on the left, then quiz me ' +
        'about it. I retrieve the most relevant passages and answer **only from them** — ' +
        'every claim shows its source page. If it is not in your documents, I say so.',
      sources: [],
    },
  ])
  const [question, setQuestion] = useState('')
  const [thinking, setThinking] = useState(false)
  const [refreshDocs, setRefreshDocs] = useState(0)
  const chatEndRef = useRef(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinking])

  async function ask(e) {
    e.preventDefault()
    const q = question.trim()
    if (!q || thinking) return
    setQuestion('')
    setMessages((m) => [...m, { role: 'user', text: q, sources: [] }])
    setThinking(true)
    try {
      const res = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Request failed')
      setMessages((m) => [
        ...m,
        { role: 'assistant', text: data.answer, sources: data.sources || [] },
      ])
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          text: `**Error:** ${err.message}`,
          sources: [],
        },
      ])
    } finally {
      setThinking(false)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <span className="logo-mark">✎</span>
        <div className="brand">
          <h1>MedDoc Q&amp;A</h1>
          <p className="tagline">RAG-grounded · answers cite source pages · no hallucinations</p>
        </div>
        <div className="header-note">⚕ study notebook mode</div>
      </header>

      <div className="layout">
        <DocumentPanel
          refreshSignal={refreshDocs}
          onUploaded={() => setRefreshDocs((n) => n + 1)}
        />

        <main className="chat-panel">
          <div className="messages">
            <div className="chat-divider">chat · answers cite pages</div>
            {messages.map((msg, i) => (
              <div key={i} className={`message ${msg.role}`}>
                <div className="bubble">
                  <ReactMarkdown>{msg.text}</ReactMarkdown>
                  {msg.sources?.length > 0 && <Sources sources={msg.sources} />}
                </div>
              </div>
            ))}
            {thinking && (
              <div className="message assistant">
                <div className="bubble typing">
                  <span></span><span></span><span></span>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <form className="chat-input" onSubmit={ask}>
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. what are the warning signs of severe dengue?"
              disabled={thinking}
            />
            <button type="submit" disabled={thinking || !question.trim()}>
              Ask
            </button>
          </form>
          <p className="input-hint">press Enter to send · answers come only from your uploaded documents</p>
        </main>
      </div>
    </div>
  )
}

function Sources({ sources }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="sources">
      <button onClick={() => setOpen(!open)}>
        📎 SOURCES ({sources.length}) {open ? '▾' : '▸'}
      </button>
      {open && (
        <ul>
          {sources.map((s, i) => (
            <li key={i}>
              <div className="source-meta">
                <span className="page-badge">p.{s.page}</span>
                <span>{s.document_name}</span>
              </div>
              <p>{s.text.slice(0, 300)}{s.text.length > 300 ? '…' : ''}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
