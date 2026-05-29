export function wsUrl(path: string, sessionId: string, base?: string): string {
  const root =
    base ??
    (import.meta.env.VITE_WS_BASE as string | undefined) ??
    `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`
  return `${root}${path}?session_id=${encodeURIComponent(sessionId)}`
}

export function resolveWsUrl(sessionId: string, base?: string): string {
  return wsUrl('/ws/transcript', sessionId, base)
}
