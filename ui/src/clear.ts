import { resolveHttpBase } from './ask'

export async function postClear(sessionId: string, base?: string): Promise<void> {
  const res = await fetch(
    `${resolveHttpBase(base)}/clear?session_id=${encodeURIComponent(sessionId)}`,
    { method: 'POST' },
  )
  if (!res.ok) {
    throw new Error(`clear failed: ${res.status}`)
  }
}
