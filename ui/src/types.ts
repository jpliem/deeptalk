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

export interface SearchPayload {
  answer?: string
  citations?: Citation[]
  model?: string
}

export interface Artifact {
  id: string
  session_id: string
  agent: string
  status: 'done' | 'error'
  title: string
  payload: SearchPayload
  created_at: number
  latency_ms: number | null
  error: string | null
}
