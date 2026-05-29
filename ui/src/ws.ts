export function resolveWsUrl(sessionId: string, base?: string): string {
  const root =
    base ??
    (import.meta.env.VITE_WS_BASE as string | undefined) ??
    `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`
  return `${root}/ws/transcript?session_id=${encodeURIComponent(sessionId)}`
}
