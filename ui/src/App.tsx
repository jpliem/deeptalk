import { useState } from 'react'
import { useTranscript } from './useTranscript'
import { useArtifacts } from './useArtifacts'
import { TranscriptPane } from './TranscriptPane'
import { ArtifactCard } from './ArtifactCard'
import { AskBox } from './AskBox'
import { postAsk } from './ask'
import { WikiPanel } from './WikiPanel'
import { postFinalize, getWiki } from './wiki'

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

  async function handleFinalize() {
    await postFinalize(SESSION_ID)
    return getWiki(SESSION_ID)
  }

  return (
    <main className="app">
      <header className="app-header">
        <h1>DeepTalk</h1>
        <span className="session">session · {SESSION_ID}</span>
      </header>
      <div className="panes">
        <section className="pane">
          <h2 className="pane-title">Transcript</h2>
          <TranscriptPane events={events} onLineClick={handleAsk} />
        </section>
        <section className="pane">
          <h2 className="pane-title">Insights</h2>
          <AskBox onAsk={handleAsk} pending={pending} />
          <div className="cards">
            {artifacts.length === 0 && (
              <p className="cards-empty">Ask a question to get a sourced answer…</p>
            )}
            {artifacts.map((a) => (
              <ArtifactCard key={a.id} artifact={a} />
            ))}
          </div>
        </section>
      </div>
      <WikiPanel onFinalize={handleFinalize} />
    </main>
  )
}
