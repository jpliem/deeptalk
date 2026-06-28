import { useState } from 'react'
import type { Wiki } from './types'

function Section({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <div className="wiki-section">
      <h4 className="wiki-section-title">{label}</h4>
      <ul className="wiki-items">
        {items.map((it, i) => (
          <li key={i}>{it}</li>
        ))}
      </ul>
    </div>
  )
}

export function WikiPanel({
  onFinalize,
}: {
  onFinalize: () => Promise<Wiki | null>
}) {
  const [wiki, setWiki] = useState<Wiki | null>(null)
  const [building, setBuilding] = useState(false)
  const [open, setOpen] = useState(false)

  async function build() {
    setBuilding(true)
    try {
      const result = await onFinalize()
      if (result) {
        setWiki(result)
        setOpen(true)
      }
    } finally {
      setBuilding(false)
    }
  }

  const hasContent =
    wiki &&
    (wiki.topics.length > 0 ||
      wiki.decisions.length > 0 ||
      wiki.action_items.length > 0)

  return (
    <div className="sidebar-section">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
        <span className="sidebar-section-title">Session Wiki</span>
        <button
          className="sidebar-btn"
          onClick={build}
          disabled={building}
          style={{ width: 'auto', padding: '0.3rem 0.6rem', margin: 0, fontSize: '0.75rem' }}
        >
          {building ? 'Building…' : 'Build'}
        </button>
      </div>

      {hasContent && (
        <button
          className="sidebar-btn"
          onClick={() => setOpen(!open)}
          style={{ margin: 0 }}
        >
          {open ? '▾ Hide wiki' : '▸ Show wiki'}
        </button>
      )}

      <div className={`wiki-collapsible${open ? '' : ' closed'}`}>
        <div style={{ marginTop: '0.5rem' }}>
          <Section label="Topics" items={wiki?.topics ?? []} />
          <Section label="Decisions" items={wiki?.decisions ?? []} />
          <Section label="Action items" items={wiki?.action_items ?? []} />
        </div>
      </div>
    </div>
  )
}
