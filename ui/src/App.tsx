import { useTranscript } from './useTranscript'
import { TranscriptPane } from './TranscriptPane'

const SESSION_ID =
  new URLSearchParams(window.location.search).get('session') ?? 'demo'

export default function App() {
  const events = useTranscript(SESSION_ID)
  return (
    <main className="app">
      <header className="app-header">
        <h1>DeepTalk</h1>
        <span className="session">session · {SESSION_ID}</span>
      </header>
      <TranscriptPane events={events} />
    </main>
  )
}
