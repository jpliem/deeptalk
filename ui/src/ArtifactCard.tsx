import type { Artifact } from './types'

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
      ) : (
        <>
          {artifact.payload.answer && <p className="card-answer">{artifact.payload.answer}</p>}
          {artifact.payload.citations && artifact.payload.citations.length > 0 && (
            <ul className="card-sources">
              {artifact.payload.citations.map((c, i) => (
                <li key={i}>
                  <a href={c.url} target="_blank" rel="noopener noreferrer">
                    {c.title}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </article>
  )
}
