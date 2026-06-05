import { useState } from 'react'
import { useTranscript } from './useTranscript'
import { useArtifacts } from './useArtifacts'
import { TranscriptPane } from './TranscriptPane'
import { ArtifactCard } from './ArtifactCard'
import { AskBox } from './AskBox'
import { AudioBar } from './AudioBar'
import { WikiPanel } from './WikiPanel'
import { postAsk } from './ask'
import { postUpload } from './upload'
import { postFinalize, getWiki } from './wiki'
import { postClear } from './clear'

const SESSION_ID =
  new URLSearchParams(window.location.search).get('session') ?? 'demo'

export default function App() {
  const events = useTranscript(SESSION_ID)
  const artifacts = useArtifacts(SESSION_ID)
  const [pending, setPending] = useState(false)

  async function handleAsk(query: string) {
    setPending(true)
    try {
      await postAsk(SESSION_ID, query)
    } finally {
      setPending(false)
    }
  }

  async function handleUpload(file: File) {
    await postUpload(SESSION_ID, file)
  }

  async function handleClear() {
    if (
      confirm(
        'Are you sure you want to clean this session? This will delete all transcripts, insights, and the wiki.'
      )
    ) {
      await postClear(SESSION_ID)
      window.location.reload()
    }
  }

  async function handleFinalize() {
    await postFinalize(SESSION_ID)
    return getWiki(SESSION_ID)
  }

  const live = events.length > 0

  return (
    <main className="app">
      <header className="app-header">
        <div className="brand">
          <span className="dot" data-live={live} />
          <h1>DeepTalk</h1>
        </div>
        <div className="header-right">
          <button className="btn-clear" onClick={handleClear}>
            Clean Session
          </button>
          <AudioBar onUpload={handleUpload} sessionId={SESSION_ID} />
          <span className="session">session · {SESSION_ID}</span>
        </div>
      </header>

      <div className="panes">
        <section className="pane">
          <div className="pane-head">
            <h2 className="pane-title">Transcript</h2>
            <span className="count">{events.length}</span>
          </div>
          <TranscriptPane events={events} onLineClick={handleAsk} />
        </section>

        <section className="pane">
          <div className="pane-head">
            <h2 className="pane-title">Insights</h2>
            <span className="count">{artifacts.length}</span>
          </div>
          <AskBox onAsk={handleAsk} pending={pending} />
          <div className="cards">
            {artifacts.length === 0 && (
              <p className="cards-empty">
                Upload audio or ask a question — answers, pros/cons, plans and diagrams appear here live.
              </p>
            )}
            {[...artifacts].reverse().map((a) => (
              <ArtifactCard key={a.id} artifact={a} />
            ))}
          </div>
        </section>
      </div>

      <WikiPanel onFinalize={handleFinalize} />
    </main>
  )
}
