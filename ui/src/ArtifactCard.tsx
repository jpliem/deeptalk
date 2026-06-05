import { useEffect, useRef } from 'react'
import type { Artifact } from './types'

function SearchBody({ a }: { a: Artifact }) {
  return (
    <>
      {a.payload.answer && <p className="card-answer">{a.payload.answer}</p>}
      {a.payload.citations && a.payload.citations.length > 0 && (
        <ul className="card-sources">
          {a.payload.citations.map((c, i) => (
            <li key={i}>
              <a href={c.url} target="_blank" rel="noopener noreferrer">
                {c.title}
              </a>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}

function ProsConsBody({ a }: { a: Artifact }) {
  return (
    <>
      <div className="proscons">
        <div className="pros">
          <h4>Pros</h4>
          <ul>
            {(a.payload.pros ?? []).map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </div>
        <div className="cons">
          <h4>Cons</h4>
          <ul>
            {(a.payload.cons ?? []).map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      </div>
      {a.payload.recommendation && (
        <p className="card-reco">
          <strong>Recommendation:</strong> {a.payload.recommendation}
        </p>
      )}
    </>
  )
}

function PlanningBody({ a }: { a: Artifact }) {
  return (
    <ol className="card-steps">
      {(a.payload.steps ?? []).map((s, i) => (
        <li key={i}>{s}</li>
      ))}
    </ol>
  )
}

function MockupBody({ a }: { a: Artifact }) {
  const ref = useRef<HTMLPreElement>(null)
  const diagram = a.payload.diagram ?? ''

  useEffect(() => {
    const node = ref.current
    if (!node || !diagram) return
    let cancelled = false
    void (async () => {
      try {
        const mermaid = (await import('mermaid')).default
        if (cancelled) return
        mermaid.initialize({ startOnLoad: false, theme: 'dark' })
        await mermaid.run({ nodes: [node] })
      } catch {
        // leave the raw mermaid source visible as a fallback
      }
    })()
    return () => {
      cancelled = true
    }
  }, [diagram])

  return (
    <>
      {a.payload.caption && <p className="card-answer">{a.payload.caption}</p>}
      <pre ref={ref} className="mermaid mockup-diagram">
        {diagram}
      </pre>
    </>
  )
}

function PendingBody({ agent }: { agent: string }) {
  if (agent === 'proscons') {
    return (
      <div className="skeleton-body proscons">
        <div className="pros">
          <div className="skeleton-line title" />
          <div className="skeleton-line" />
          <div className="skeleton-line" />
        </div>
        <div className="cons">
          <div className="skeleton-line title" />
          <div className="skeleton-line" />
          <div className="skeleton-line" />
        </div>
      </div>
    )
  }
  if (agent === 'planning') {
    return (
      <div className="skeleton-body card-steps">
        <div className="skeleton-line" style={{ width: '80%' }} />
        <div className="skeleton-line" style={{ width: '70%' }} />
        <div className="skeleton-line" style={{ width: '60%' }} />
      </div>
    )
  }
  if (agent === 'mockup') {
    return (
      <div className="skeleton-body">
        <div className="skeleton-line" style={{ width: '40%' }} />
        <div className="skeleton-box" style={{ height: '120px', marginTop: '0.5rem' }} />
      </div>
    )
  }
  return (
    <div className="skeleton-body">
      <div className="skeleton-line" />
      <div className="skeleton-line" style={{ width: '85%' }} />
      <div className="skeleton-line" style={{ width: '60%' }} />
    </div>
  )
}

export function ArtifactCard({ artifact }: { artifact: Artifact }) {
  const isError = artifact.status === 'error'
  const isPending = artifact.status === 'pending'
  return (
    <article className={`card ${isError ? 'error' : ''} ${isPending ? 'pending' : ''}`}>
      <header className="card-head">
        <span className="badge">{artifact.agent}</span>
        <h3 className="card-title">{artifact.title}</h3>
      </header>
      {isError ? (
        <p className="card-error">{artifact.error ?? 'Something went wrong'}</p>
      ) : isPending ? (
        <PendingBody agent={artifact.agent} />
      ) : artifact.agent === 'proscons' ? (
        <ProsConsBody a={artifact} />
      ) : artifact.agent === 'planning' ? (
        <PlanningBody a={artifact} />
      ) : artifact.agent === 'mockup' ? (
        <MockupBody a={artifact} />
      ) : (
        <SearchBody a={artifact} />
      )}
    </article>
  )
}
