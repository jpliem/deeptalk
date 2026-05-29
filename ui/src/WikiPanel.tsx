import { useState } from 'react'
import type { Wiki } from './types'

function Section({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) {
    return null
  }
  return (
    <div className="wiki-section">
      <h3>{label}</h3>
      <ul>
        {items.map((it, i) => (
          <li key={i}>{it}</li>
        ))}
      </ul>
    </div>
  )
}

export function WikiPanel({ onFinalize }: { onFinalize: () => Promise<Wiki | null> }) {
  const [wiki, setWiki] = useState<Wiki | null>(null)
  const [building, setBuilding] = useState(false)

  async function build() {
    setBuilding(true)
    try {
      setWiki(await onFinalize())
    } finally {
      setBuilding(false)
    }
  }

  return (
    <section className="wiki">
      <div className="wiki-head">
        <h2 className="pane-title">Session Wiki</h2>
        <button className="ask-button" onClick={build} disabled={building}>
          {building ? 'Building…' : 'Build wiki'}
        </button>
      </div>
      {wiki ? (
        <div className="wiki-body">
          <Section label="Topics" items={wiki.topics} />
          <Section label="Decisions" items={wiki.decisions} />
          <Section label="Action items" items={wiki.action_items} />
        </div>
      ) : (
        <p className="cards-empty">Build a wiki to summarize the session…</p>
      )}
    </section>
  )
}
