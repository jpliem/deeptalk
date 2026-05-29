import { resolveHttpBase } from './ask'
import type { Wiki } from './types'

export async function postFinalize(sessionId: string, base?: string): Promise<void> {
  const res = await fetch(`${resolveHttpBase(base)}/finalize`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  if (!res.ok) {
    throw new Error(`finalize failed: ${res.status}`)
  }
}

export async function getWiki(sessionId: string, base?: string): Promise<Wiki | null> {
  const res = await fetch(
    `${resolveHttpBase(base)}/wiki?session_id=${encodeURIComponent(sessionId)}`,
  )
  if (res.status === 404) {
    return null
  }
  if (!res.ok) {
    throw new Error(`get wiki failed: ${res.status}`)
  }
  return res.json() as Promise<Wiki>
}
