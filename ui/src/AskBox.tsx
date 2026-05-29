import { useState, type FormEvent } from 'react'

export function AskBox({
  onAsk,
  pending,
}: {
  onAsk: (query: string) => void | Promise<void>
  pending: boolean
}) {
  const [query, setQuery] = useState('')

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = query.trim()
    if (!trimmed || pending) {
      return
    }
    await onAsk(trimmed)
    setQuery('')
  }

  return (
    <form className="ask-box" onSubmit={handleSubmit}>
      <input
        className="ask-input"
        placeholder="Ask the meeting assistant…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        disabled={pending}
      />
      <button className="ask-button" type="submit" disabled={pending}>
        {pending ? 'Asking…' : 'Ask'}
      </button>
    </form>
  )
}
