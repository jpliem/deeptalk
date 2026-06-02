import { useRef, useState } from 'react'

export function AudioBar({ onUpload }: { onUpload: (file: File) => Promise<void> }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState<string | null>(null)

  async function handleFile(file: File) {
    setName(file.name)
    setBusy(true)
    try {
      await onUpload(file)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="audiobar">
      <button
        className="audiobar-btn"
        onClick={() => inputRef.current?.click()}
        disabled={busy}
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
