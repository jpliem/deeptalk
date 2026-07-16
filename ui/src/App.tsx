import { useEffect, useRef, useState } from 'react'
import { useTranscript } from './useTranscript'
import { useArtifacts } from './useArtifacts'
import { useTimeline } from './useTimeline'
import { useSessions } from './useSessions'
import { MessageBubble } from './MessageBubble'
import { ArtifactCard } from './ArtifactCard'
import { InputBar } from './InputBar'
import { TimelinePanel } from './TimelinePanel'
import { WikiPanel } from './WikiPanel'
import { postAsk } from './ask'
import { postUpload } from './upload'
import { postFinalize, getWiki } from './wiki'
import { downloadReport } from './report'
import { postClear } from './clear'
import type { Wiki } from './types'

const rawSession = new URLSearchParams(window.location.search).get('session')
const SESSION_ID = rawSession && rawSession.length > 0 ? rawSession : 'demo'

export default function App() {
  const events = useTranscript(SESSION_ID)
  const artifacts = useArtifacts(SESSION_ID)
  const timelineEntries = useTimeline(SESSION_ID)
  const { sessions, currentName, createSession, switchSession, removeSession } =
    useSessions(SESSION_ID)
  const [userMessages, setUserMessages] = useState<string[]>([])
  const [pending, setPending] = useState(false)
  const [suggestedQuery, setSuggestedQuery] = useState<string>()
  const [appError, setAppError] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const feedRef = useRef<HTMLDivElement>(null)

  const live = events.length > 0

  // Auto-scroll to bottom when new content arrives
  useEffect(() => {
    const el = feedRef.current
    if (!el) return
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 150
    if (isNearBottom) {
      requestAnimationFrame(() => {
        el.scrollTop = el.scrollHeight
      })
    }
  }, [events.length, artifacts.length, userMessages.length])

  async function handleAsk(query: string) {
    setUserMessages((prev) => [...prev, query])
    setPending(true)
    try {
      await postAsk(SESSION_ID, query)
    } finally {
      setPending(false)
    }
  }

  async function handleUpload(file: File) {
    try {
      await postUpload(SESSION_ID, file)
    } catch {
      setAppError('Upload failed. Check the connection and try again.')
    }
  }

  async function handleClear() {
    if (
      confirm(
        'Are you sure you want to clean this session? This will delete all transcripts, insights, and the wiki.',
      )
    ) {
      await postClear(SESSION_ID)
      removeSession(SESSION_ID)
      window.location.reload()
    }
  }

  async function handleFinalize(): Promise<Wiki | null> {
    await postFinalize(SESSION_ID)
    return getWiki(SESSION_ID)
  }

  async function handleDownloadReport() {
    try {
      await downloadReport(SESSION_ID)
    } catch (err) {
      setAppError(err instanceof Error ? err.message : 'Report download failed.')
    }
  }

  function handleBubbleClick(text: string) {
    setSuggestedQuery(text)
  }

  function handleJumpToTime(ts: number) {
    const el = feedRef.current
    if (!el) return
    // Find the first MessageBubble element whose data-ts matches
    const children = el.querySelectorAll('.message.transcript')
    for (const child of children) {
      const htmlChild = child as HTMLElement
      const tsAttr = htmlChild.getAttribute('data-ts')
      if (tsAttr && parseFloat(tsAttr) >= ts) {
        htmlChild.scrollIntoView({ behavior: 'smooth', block: 'center' })
        htmlChild.style.outline = '2px solid var(--accent)'
        htmlChild.style.outlineOffset = '2px'
        setTimeout(() => {
          htmlChild.style.outline = ''
          htmlChild.style.outlineOffset = ''
        }, 2000)
        return
      }
    }
  }

  return (
    <>
      {/* Mobile overlay */}
      <div
        className={`sidebar-overlay${sidebarOpen ? ' visible' : ''}`}
        onClick={() => setSidebarOpen(false)}
      />

      {/* Mobile toggle */}
      <button className="sidebar-toggle" onClick={() => setSidebarOpen(true)}>
        ☰
      </button>

      <div className="app">
        {/* Sidebar */}
        <aside className={`sidebar${sidebarOpen ? ' open' : ''}`}>
          <div className="sidebar-header">
            <span className={`live-dot${live ? ' active' : ''}`} />
            <h1 className="sidebar-logo">DeepTalk</h1>
          </div>

          <div className="sidebar-section">
            <div className="sidebar-section-title">Current Session</div>
            <div className="sidebar-label">{currentName}</div>
          </div>

          <div className="sidebar-section">
            <button className="sidebar-btn" onClick={createSession}>
              ＋ New session
            </button>
            <button className="sidebar-btn danger" onClick={handleClear}>
              ✕ Clear session
            </button>
          </div>

          {/* Session list */}
          <div className="sidebar-section">
            <div className="sidebar-section-title">Past Sessions</div>
            <div className="session-list">
              {sessions
                .filter((s) => s.id !== SESSION_ID)
                .slice(0, 10)
                .map((s) => (
                  <div key={s.id} className="session-list-item">
                    <button
                      className="session-list-btn"
                      onClick={() => switchSession(s.id)}
                    >
                      {s.name}
                    </button>
                    <button
                      className="session-list-del"
                      onClick={(e) => {
                        e.stopPropagation()
                        removeSession(s.id)
                      }}
                      title="Remove from list"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              {sessions.filter((s) => s.id !== SESSION_ID).length === 0 && (
                <div className="session-list-empty">No past sessions</div>
              )}
            </div>
          </div>

          <TimelinePanel
            entries={timelineEntries}
            onJumpToTime={handleJumpToTime}
          />

          <div style={{ flex: 1 }} />

          <WikiPanel onFinalize={handleFinalize} onDownloadReport={handleDownloadReport} />
        </aside>

        {/* Chat Area */}
        <div className="chat-area">
          <div className="chat-feed" ref={feedRef}>
            {events.length === 0 && artifacts.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">🎙️</div>
                <p className="empty-state-text">
                  Upload audio to start transcribing, or ask a question about the meeting.
                </p>
              </div>
            ) : (
              <div className="chat-feed-inner">
                {/* Transcript events */}
                {events.map((e, i) => (
                  <MessageBubble
                    key={`t-${i}`}
                    event={e}
                    onClick={handleBubbleClick}
                  />
                ))}

                {/* User messages */}
                {userMessages.map((q, i) => (
                  <div key={`u-${i}`} className="message user">
                    <div className="message-content">{q}</div>
                  </div>
                ))}

                {/* Artifact cards */}
                {[...artifacts].reverse().map((a) => (
                  <ArtifactCard key={a.id} artifact={a} />
                ))}
              </div>
            )}
          </div>

          {appError && (
            <div className="app-error" onClick={() => setAppError(null)}>
              {appError}
            </div>
          )}
          <InputBar
            sessionId={SESSION_ID}
            onAsk={handleAsk}
            onUpload={handleUpload}
            pending={pending}
            defaultQuery={suggestedQuery}
            onError={setAppError}
          />
        </div>
      </div>
    </>
  )
}
