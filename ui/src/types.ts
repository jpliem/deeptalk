export interface TranscriptEvent {
  session_id: string
  ts: number
  text: string
  is_final: boolean
  source: 'live' | 'diarized'
  speaker: number | null
  span_id: string | null
}
