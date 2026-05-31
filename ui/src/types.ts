export interface TranscriptEvent {
  session_id: string
  ts: number
  text: string
  is_final: boolean
  source: 'live' | 'diarized'
  speaker: number | null
  span_id: string | null
}

export interface Citation {
  title: string
  url: string
}

export interface ArtifactPayload {
  answer?: string
  citations?: Citation[]
  model?: string
  pros?: string[]
  cons?: string[]
  recommendation?: string
  steps?: string[]
  diagram?: string
  caption?: string
}

export interface Artifact {
  id: string
  session_id: string
  agent: string
  status: 'done' | 'error'
  title: string
  payload: ArtifactPayload
  created_at: number
  latency_ms: number | null
  error: string | null
}

export interface Wiki {
  session_id: string
  topics: string[]
  decisions: string[]
  action_items: string[]
  created_at: number
}
