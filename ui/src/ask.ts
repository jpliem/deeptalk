export function resolveHttpBase(base?: string): string {
  return (
    base ??
    (import.meta.env.VITE_HTTP_BASE as string | undefined) ??
    window.location.origin
  )
}

export interface AskResult {
  id: string
  status: string
}

export async function postAsk(
  sessionId: string,
  query: string,
  base?: string,
): Promise<AskResult> {
  const res = await fetch(`${resolveHttpBase(base)}/ask`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, query }),
  })
  if (!res.ok) {
    throw new Error(`ask failed: ${res.status}`)
  }
  return res.json() as Promise<AskResult>
}
