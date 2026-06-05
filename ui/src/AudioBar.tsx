import { useRef, useState, useEffect } from 'react'
import { wsUrl } from './ws'

export function AudioBar({
  onUpload,
  sessionId = 'demo',
  wsBase,
}: {
  onUpload: (file: File) => Promise<void>
  sessionId?: string
  wsBase?: string
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState<string | null>(null)
  const [micActive, setMicActive] = useState(false)

  // References for live mic streaming
  const streamRef = useRef<MediaStream | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)

  async function handleFile(file: File) {
    setName(file.name)
    setBusy(true)
    try {
      await onUpload(file)
    } finally {
      setBusy(false)
    }
  }

  async function startStreaming() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const ws = new WebSocket(wsUrl('/ws/audio-stream', sessionId, wsBase))
      wsRef.current = ws

      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)({
        sampleRate: 16000,
      })
      audioCtxRef.current = audioCtx

      const source = audioCtx.createMediaStreamSource(stream)
      sourceRef.current = source

      const processor = audioCtx.createScriptProcessor(4096, 1, 1)
      processorRef.current = processor

      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0)
        const pcmData = new Int16Array(inputData.length)
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]))
          pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7fff
        }
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(pcmData.buffer)
        }
      }

      source.connect(processor)
      processor.connect(audioCtx.destination)
      setMicActive(true)
    } catch (err) {
      alert('Could not start microphone: ' + err)
      stopStreaming()
    }
  }

  function stopStreaming() {
    setMicActive(false)
    if (processorRef.current) {
      try {
        processorRef.current.disconnect()
      } catch {}
      processorRef.current = null
    }
    if (sourceRef.current) {
      try {
        sourceRef.current.disconnect()
      } catch {}
      sourceRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
    if (audioCtxRef.current) {
      if (audioCtxRef.current.state !== 'closed') {
        void audioCtxRef.current.close()
      }
      audioCtxRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }

  function toggleMic() {
    if (micActive) {
      stopStreaming()
    } else {
      void startStreaming()
    }
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopStreaming()
    }
  }, [])

  return (
    <div className="audiobar">
      <button
        className={`audiobar-btn mic-btn ${micActive ? 'active' : ''}`}
        onClick={toggleMic}
        disabled={busy}
        data-testid="audio-mic-btn"
      >
        {micActive ? 'Stop Mic' : 'Start Mic'}
      </button>
      <button
        className="audiobar-btn"
        onClick={() => inputRef.current?.click()}
        disabled={busy || micActive}
      >
        {busy ? 'Transcribing…' : 'Upload audio'}
      </button>
      <input
        ref={inputRef}
        data-testid="audio-file-input"
        type="file"
        accept="audio/*,.mp3,.wav,.m4a"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) void handleFile(f)
        }}
      />
      {name && <span className="audiobar-name">{busy ? `${name} …` : name}</span>}
    </div>
  )
}
