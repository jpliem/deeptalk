import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { wsUrl } from './ws'

export function InputBar({
  sessionId,
  onAsk,
  onUpload,
  pending,
  defaultQuery,
}: {
  sessionId: string
  onAsk: (query: string) => Promise<void>
  onUpload: (file: File) => Promise<void>
  pending: boolean
  defaultQuery?: string
}) {
  const [value, setValue] = useState('')
  const [recording, setRecording] = useState(false)
  const textRef = useRef<HTMLTextAreaElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  // Live-streaming state
  const wsRef = useRef<WebSocket | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const ctxRef = useRef<AudioContext | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)

  // Sync defaultQuery into the textarea when it changes
  const prevDefault = useRef(defaultQuery)
  useEffect(() => {
    if (defaultQuery && defaultQuery !== prevDefault.current) {
      setValue(defaultQuery)
      prevDefault.current = defaultQuery
      textRef.current?.focus()
    }
  }, [defaultQuery])

  function autoResize() {
    const el = textRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }

  async function handleSubmit(e?: FormEvent) {
    e?.preventDefault()
    const trimmed = value.trim()
    if (!trimmed || pending) return
    setValue('')
    if (textRef.current) {
      textRef.current.style.height = 'auto'
    }
    await onAsk(trimmed)
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSubmit()
    }
  }

  function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) {
      void onUpload(file)
    }
    e.target.value = ''
  }

  async function toggleRecording() {
    if (recording) {
      // === STOP live stream ===
      processorRef.current?.disconnect()
      ctxRef.current?.close()
      streamRef.current?.getTracks().forEach((t) => t.stop())
      wsRef.current?.close()
      setRecording(false)
    } else {
      // === START live stream ===
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        streamRef.current = stream

        // Open WebSocket to the live-audio endpoint
        const ws = new WebSocket(wsUrl('/ws/live-audio', sessionId))
        ws.binaryType = 'arraybuffer'
        wsRef.current = ws

        ws.onopen = () => {
          const ctx = new AudioContext({ sampleRate: 16000 })
          ctxRef.current = ctx

          const source = ctx.createMediaStreamSource(stream)
          const processor = ctx.createScriptProcessor(4096, 1, 1)
          processorRef.current = processor

          processor.onaudioprocess = (e) => {
            const input = e.inputBuffer.getChannelData(0)
            const pcm = new Int16Array(input.length)
            for (let i = 0; i < input.length; i++) {
              pcm[i] = Math.max(-32768, Math.min(32767, input[i] * 32768))
            }
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(pcm.buffer)
            }
          }

          source.connect(processor)
          processor.connect(ctx.destination)
        }

        ws.onerror = () => {
          alert('Failed to connect live audio stream.')
          stream.getTracks().forEach((t) => t.stop())
          ctxRef.current?.close()
          setRecording(false)
        }

        setRecording(true)
      } catch {
        alert('Microphone access is needed to record audio.')
      }
    }
  }

  return (
    <div className="input-bar">
      <form className="input-form" onSubmit={handleSubmit}>
        <textarea
          ref={textRef}
          className="input-textarea"
          placeholder="Ask the meeting assistant…"
          rows={1}
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            autoResize()
          }}
          onKeyDown={handleKeyDown}
          disabled={pending}
        />
        <div className="input-actions">
          <button
            type="button"
            className={`input-btn${recording ? ' recording' : ''}`}
            title={recording ? 'Stop listening' : 'Start live listening'}
            disabled={pending}
            onClick={toggleRecording}
          >
            {recording ? '⏹' : '🎤'}
          </button>
          <button
            type="button"
            className="input-btn"
            title="Upload audio file"
            disabled={pending || recording}
            onClick={() => fileRef.current?.click()}
          >
            📎
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="audio/*,.mp3,.wav,.m4a"
            hidden
            onChange={handleFileSelected}
          />
          <button
            type="submit"
            className={`input-btn send${value.trim() ? '' : ' hidden'}`}
            disabled={pending || !value.trim()}
            title="Send"
          >
            ➤
          </button>
        </div>
      </form>
    </div>
  )
}
