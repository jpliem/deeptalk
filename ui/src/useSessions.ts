import { useCallback, useState } from 'react'

const STORAGE_KEY = 'deeptalk_sessions'

export interface SessionInfo {
  id: string
  name: string
  created_at: number
  updated_at: number
}

function loadSessions(): SessionInfo[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as SessionInfo[]) : []
  } catch {
    return []
  }
}

function saveSessions(sessions: SessionInfo[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions))
  } catch {
    // localStorage full or disabled — silently ignore
  }
}

function fmtDate(ts: number): string {
  const d = new Date(ts)
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
}

export function useSessions(currentId: string) {
  const [sessions, setSessions] = useState<SessionInfo[]>(() => {
    const existing = loadSessions()
    // Ensure current session is always in the list
    const hasCurrent = existing.some((s) => s.id === currentId)
    if (!hasCurrent) {
      const now = Date.now()
      const entry: SessionInfo = {
        id: currentId,
        name: `Session ${fmtDate(now)}`,
        created_at: now,
        updated_at: now,
      }
      const updated = [entry, ...existing]
      saveSessions(updated)
      return updated
    }
    return existing
  })

  const createSession = useCallback(() => {
    const id = generateId()
    const now = Date.now()
    const entry: SessionInfo = {
      id,
      name: `Session ${fmtDate(now)}`,
      created_at: now,
      updated_at: now,
    }
    const updated = [entry, ...loadSessions()]
    saveSessions(updated)
    setSessions(updated)
    // Navigate to new session
    window.location.href = `/?session=${id}`
  }, [])

  const switchSession = useCallback((id: string) => {
    window.location.href = `/?session=${id}`
  }, [])

  const renameSession = useCallback((id: string, name: string) => {
    const all = loadSessions()
    const idx = all.findIndex((s) => s.id === id)
    if (idx !== -1) {
      all[idx] = { ...all[idx], name, updated_at: Date.now() }
      saveSessions(all)
      setSessions(all)
    }
  }, [])

  const removeSession = useCallback((id: string) => {
    const all = loadSessions().filter((s) => s.id !== id)
    saveSessions(all)
    setSessions(all)
  }, [])

  const currentName =
    sessions.find((s) => s.id === currentId)?.name ?? 'Untitled'

  return { sessions, currentName, createSession, switchSession, renameSession, removeSession }
}
