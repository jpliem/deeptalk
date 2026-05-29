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

export function ArtifactCard({ artifact }: { artifact: Artifact }) {
  const isError = artifact.status === 'error'
  return (
    <article className={`card ${isError ? 'error' : ''}`}>
      <header className="card-head">
        <span className="badge">{artifact.agent}</span>
        <h3 className="card-title">{artifact.title}</h3>
      </header>
      {isError ? (
        <p className="card-error">{artifact.error ?? 'Something went wrong'}</p>
      ) : artifact.agent === 'proscons' ? (
        <ProsConsBody a={artifact} />
      ) : artifact.agent === 'planning' ? (
        <PlanningBody a={artifact} />
      ) : (
        <SearchBody a={artifact} />
      )}
    </article>
  )
}
