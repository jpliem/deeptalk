# DeepTalk Phase 9A — Audio Upload + Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give DeepTalk real in-browser audio input (upload mp3/wav/m4a) and a genuinely good dashboard. Add an ffmpeg decode step, a `POST /upload` endpoint that transcribes an uploaded file through the existing pipeline, a UI audio bar to upload, live "working" status, and a full visual redesign of the dashboard. Browser live-mic streaming is Phase 9B.

**Architecture:** `decode_to_wav` normalizes any audio to 16 kHz mono WAV (ffmpeg; passthrough if already conformant). `build_stt(config, audio_source=, realtime=)` is generalized so the upload handler can transcribe an arbitrary file. `POST /upload` saves the file → decodes → transcribes → emits transcript events onto the same bus (so the orchestrator + agents react exactly as for live audio). The UI gains an `AudioBar` (drag-drop / picker + status), de-duplicates artifacts by id (so re-sent artifacts can show pending→done), and is restyled into a real-time command-center layout.

**Tech Stack:** Python 3.12, FastAPI (`UploadFile`), ffmpeg (system binary), React + Vitest.

---

## Roadmap context

Phase 9A — the first UX-completeness phase beyond the spec's 8. Phases 1–8 + auto-record are on `main`. 9B (browser mic over WebSocket) follows. Real transcription still requires nemotron on the GPU box; on a no-GPU machine `DEEPTALK_STT=fake` makes upload replay the bundled fixture so the pipeline + UI are fully demoable/testable.

## File Structure (Phase 9A)

```
deeptalk/
  src/deeptalk/
    audio/decode.py             # NEW: decode_to_wav + _ffmpeg_cmd
    stt/factory.py              # MODIFY: build_stt(config, audio_source=, realtime=)
    server/app.py               # MODIFY: POST /upload, config param
    server/__main__.py          # MODIFY: pass config to create_app
  tests/
    test_decode.py              # NEW
    test_upload.py              # NEW
  ui/src/
    upload.ts                   # NEW: postUpload
    AudioBar.tsx                # NEW
    App.tsx                     # MODIFY: redesign + AudioBar + status
    useArtifacts.ts             # MODIFY: dedup by id (replace)
    styles.css                  # MODIFY: redesign
    __tests__/upload.test.ts        # NEW
    __tests__/AudioBar.test.tsx     # NEW
    __tests__/useArtifacts.test.tsx # MODIFY: dedup test
```

---

### Task 1: ffmpeg decode utility

**Files:**
- Create: `src/deeptalk/audio/decode.py`
- Test: `tests/test_decode.py`

- [ ] **Step 1: Write the failing test** — `tests/test_decode.py`:

```python
import math
import shutil
import struct
import wave

import pytest

from deeptalk.audio.decode import _ffmpeg_cmd, decode_to_wav


def _write_wav(path, seconds=0.1, rate=16000, channels=1):
    n = int(rate * seconds)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"".join(struct.pack("<h", int(1000 * math.sin(i / 5))) for i in range(n * channels)))


def test_ffmpeg_cmd_builds_16k_mono():
    cmd = _ffmpeg_cmd("in.mp3", "out.wav", rate=16000)
    assert cmd[0] == "ffmpeg"
    assert "in.mp3" in cmd and "out.wav" in cmd
    assert "16000" in cmd
    assert "1" in cmd  # mono (ac 1)


def test_decode_passthrough_for_conformant_wav(tmp_path):
    src = tmp_path / "ok.wav"
    _write_wav(src, rate=16000, channels=1)
    # already 16k mono 16-bit → returned as-is, no ffmpeg needed
    assert decode_to_wav(str(src)) == str(src)


def test_decode_nonconformant_requires_ffmpeg(tmp_path):
    src = tmp_path / "stereo.wav"
    _write_wav(src, rate=44100, channels=2)
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    out = decode_to_wav(str(src))
    assert out != str(src)
    with wave.open(out, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 16000
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_decode.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.audio.decode'`

- [ ] **Step 3: Write it** — `src/deeptalk/audio/decode.py`:

```python
from __future__ import annotations

import subprocess
import tempfile
import wave


def _ffmpeg_cmd(src: str, dst: str, rate: int = 16000) -> list[str]:
    return [
        "ffmpeg", "-y", "-i", src,
        "-ac", "1",            # mono
        "-ar", str(rate),      # sample rate
        "-sample_fmt", "s16",  # 16-bit
        dst,
    ]


def _is_conformant(path: str, rate: int) -> bool:
    try:
        with wave.open(path, "rb") as wf:
            return (
                wf.getnchannels() == 1
                and wf.getframerate() == rate
                and wf.getsampwidth() == 2
            )
    except (wave.Error, EOFError, OSError):
        return False


def decode_to_wav(src: str, rate: int = 16000) -> str:
    """Return a path to a 16 kHz mono 16-bit WAV. Passthrough if `src` already is one;
    otherwise transcode with ffmpeg (supports mp3/m4a/wav/etc.)."""
    if _is_conformant(src, rate):
        return src
    dst = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    subprocess.run(_ffmpeg_cmd(src, dst, rate), check=True, capture_output=True)
    return dst
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_decode.py -v`
Expected: PASS (3 passed, or 2 passed + 1 skipped if ffmpeg absent on the dev box).

- [ ] **Step 5: Commit**

```bash
git add src/deeptalk/audio/decode.py tests/test_decode.py
git commit -m "feat: add ffmpeg decode_to_wav (mp3/m4a/wav -> 16k mono)"
```

---

### Task 2: build_stt override + POST /upload

**Files:**
- Modify: `src/deeptalk/stt/factory.py`, `src/deeptalk/server/app.py`, `src/deeptalk/server/__main__.py`
- Test: `tests/test_upload.py`

- [ ] **Step 1: Generalize `build_stt`** — in `src/deeptalk/stt/factory.py`, change the signature and body:

```python
def build_stt(
    config: Config,
    audio_source: "AudioSource | None" = None,
    realtime: bool = True,
) -> SttLive:
    if config.stt == "fake":
        return FakeSttLive(
            session_id=config.session_id,
            fixture_path=config.fixture_path,
            realtime=realtime,
        )
    if config.stt == "nemotron":
        from deeptalk.stt.nemo_recognizer import NemoCacheAwareRecognizer
        from deeptalk.stt.nemotron import NemotronSttLive

        audio = audio_source if audio_source is not None else build_audio_source(config)
        return NemotronSttLive(
            session_id=config.session_id,
            audio_source=audio,
            recognizer=NemoCacheAwareRecognizer(),
        )
    raise ValueError(f"unknown stt: {config.stt}")
```
(`AudioSource` is already imported in this module. The lifespan still calls `build_stt(config)` → `realtime=True` default, unchanged behavior.)

- [ ] **Step 2: Write the failing test** — `tests/test_upload.py`:

```python
import math
import struct
import wave

from fastapi.testclient import TestClient

from deeptalk.bus import EventBus
from deeptalk.config import Config
from deeptalk.server.app import create_app
from deeptalk.transcript.store import TranscriptStore


def _wav_bytes(seconds=0.1, rate=16000):
    import io

    n = int(rate * seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"".join(struct.pack("<h", int(1000 * math.sin(i / 5))) for i in range(n)))
    return buf.getvalue()


def test_upload_transcribes_into_session(tmp_path):
    # fake STT replays the bundled fixture (3 lines) for the uploaded file
    cfg = Config.from_env({"DEEPTALK_STT": "fake", "DEEPTALK_SESSION_ID": "demo"})
    store = TranscriptStore(str(tmp_path / "t.db"))
    app = create_app(store=store, bus=EventBus(), config=cfg)
    client = TestClient(app)

    resp = client.post(
        "/upload?session_id=demo",
        files={"file": ("clip.wav", _wav_bytes(), "audio/wav")},
    )
    assert resp.status_code == 200
    assert resp.json()["events"] >= 1
    assert len(store.all_events("demo")) >= 1


def test_upload_503_without_config(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    app = create_app(store=store, bus=EventBus())  # no config
    client = TestClient(app)
    resp = client.post("/upload", files={"file": ("c.wav", _wav_bytes(), "audio/wav")})
    assert resp.status_code == 503
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_upload.py -v`
Expected: FAIL — `create_app()` has no `config` param / no `/upload` route.

- [ ] **Step 4: Add `/upload` to `src/deeptalk/server/app.py`**

Add imports near the top:
```python
import shutil
import tempfile
from pathlib import Path as _Path2

from fastapi import File, UploadFile

from deeptalk.audio.decode import decode_to_wav
from deeptalk.audio.file_source import FileAudioSource
from deeptalk.stt.factory import build_stt
```
Add `config: "Config | None" = None` to the `create_app` signature (after `gpu_lease`). Add a TYPE_CHECKING import for `Config` (or a string annotation) — to avoid a circular import, import inside a guard at top:
```python
from deeptalk.config import Config
```
(That import is safe — config.py has no server imports.) Then register the route before the UI mount:
```python
    if config is not None:

        @app.post("/upload")
        async def upload(file: UploadFile = File(...), session_id: str = "default") -> dict[str, int]:
            suffix = _Path2(file.filename or "audio").suffix or ".bin"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                shutil.copyfileobj(file.file, tmp)
                src = tmp.name
            wav = decode_to_wav(src)
            stt = build_stt(config, audio_source=FileAudioSource(wav), realtime=False)
            count = 0
            async for ev in stt.stream():
                store.append(ev)
                await bus.publish(ev)
                count += 1
            return {"events": count}
```
(`python-multipart` is required by FastAPI for form/file parsing — add it: `uv add python-multipart`.)

- [ ] **Step 5: Pass `config` from the entrypoint** — in `src/deeptalk/server/__main__.py`, add `config=config,` to the `create_app(...)` call.

- [ ] **Step 6: Run to verify it passes + full suite**

Run: `uv run pytest tests/test_upload.py -v && uv run pytest -q`
Expected: upload 2 passed; full suite green.

- [ ] **Step 7: Commit**

```bash
git add src/deeptalk/stt/factory.py src/deeptalk/server/app.py src/deeptalk/server/__main__.py pyproject.toml uv.lock tests/test_upload.py
git commit -m "feat: POST /upload transcribes an uploaded audio file through the pipeline"
```

---

### Task 3: UI upload helper + AudioBar

**Files:**
- Create: `ui/src/upload.ts`, `ui/src/AudioBar.tsx`
- Test: `ui/src/__tests__/upload.test.ts`, `ui/src/__tests__/AudioBar.test.tsx`

- [ ] **Step 1: Write the failing upload-helper test** — `ui/src/__tests__/upload.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { postUpload } from '../upload'

beforeEach(() => vi.restoreAllMocks())

describe('postUpload', () => {
  it('POSTs the file as multipart to /upload', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ events: 3 }) })
    vi.stubGlobal('fetch', fetchMock)
    const file = new File([new Uint8Array([1, 2, 3])], 'clip.wav', { type: 'audio/wav' })
    const out = await postUpload('demo', file, 'http://h')
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('http://h/upload?session_id=demo')
    expect(opts.method).toBe('POST')
    expect(opts.body).toBeInstanceOf(FormData)
    expect(out).toEqual({ events: 3 })
  })

  it('throws on non-ok', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))
    const file = new File([new Uint8Array([1])], 'c.wav')
    await expect(postUpload('demo', file, 'http://h')).rejects.toThrow('500')
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ui && npx vitest run src/__tests__/upload.test.ts`
Expected: FAIL — cannot resolve `../upload`.

- [ ] **Step 3: Create `ui/src/upload.ts`**

```ts
import { resolveHttpBase } from './ask'

export interface UploadResult {
  events: number
}

export async function postUpload(
  sessionId: string,
  file: File,
  base?: string,
): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(
    `${resolveHttpBase(base)}/upload?session_id=${encodeURIComponent(sessionId)}`,
    { method: 'POST', body: form },
  )
  if (!res.ok) {
    throw new Error(`upload failed: ${res.status}`)
  }
  return res.json() as Promise<UploadResult>
}
```

- [ ] **Step 4: Write the failing AudioBar test** — `ui/src/__tests__/AudioBar.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AudioBar } from '../AudioBar'

describe('AudioBar', () => {
  it('calls onUpload with the chosen file', async () => {
    const onUpload = vi.fn().mockResolvedValue(undefined)
    render(<AudioBar onUpload={onUpload} />)
    const file = new File([new Uint8Array([1, 2])], 'clip.mp3', { type: 'audio/mpeg' })
    const input = screen.getByTestId('audio-file-input') as HTMLInputElement
    await userEvent.upload(input, file)
    expect(onUpload).toHaveBeenCalledTimes(1)
    expect(onUpload.mock.calls[0][0].name).toBe('clip.mp3')
  })

  it('shows a working state while uploading', async () => {
    let resolve: () => void = () => {}
    const onUpload = vi.fn().mockReturnValue(new Promise<void>((r) => (resolve = r)))
    render(<AudioBar onUpload={onUpload} />)
    const file = new File([new Uint8Array([1])], 'c.wav')
    await userEvent.upload(screen.getByTestId('audio-file-input'), file)
    expect(screen.getByText(/transcribing/i)).toBeInTheDocument()
    resolve()
  })
})
```

- [ ] **Step 5: Run to verify it fails**

Run: `cd ui && npx vitest run src/__tests__/AudioBar.test.tsx`
Expected: FAIL — cannot resolve `../AudioBar`.

- [ ] **Step 6: Create `ui/src/AudioBar.tsx`**

```tsx
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
```

- [ ] **Step 7: Run to verify it passes**

Run: `cd ui && npx vitest run src/__tests__/upload.test.ts src/__tests__/AudioBar.test.tsx`
Expected: PASS (upload 2 + AudioBar 2).

- [ ] **Step 8: Commit**

```bash
git add ui/src/upload.ts ui/src/AudioBar.tsx ui/src/__tests__/upload.test.ts ui/src/__tests__/AudioBar.test.tsx
git commit -m "feat(ui): add audio upload helper and AudioBar"
```

---

### Task 4: useArtifacts dedup-by-id + dashboard redesign

**Files:**
- Modify: `ui/src/useArtifacts.ts`, `ui/src/App.tsx`, `ui/src/styles.css`
- Test: `ui/src/__tests__/useArtifacts.test.tsx`

- [ ] **Step 1: Add a failing dedup test** — append to `ui/src/__tests__/useArtifacts.test.tsx`:

```tsx
it('replaces an artifact when a newer one with the same id arrives', async () => {
  const { result } = renderHook(() => useArtifacts('demo', 'ws://x'))
  const sock = FakeWebSocket.instances[0]
  sendArtifact(sock, { id: 'a1', status: 'pending', title: 'q' })
  sendArtifact(sock, { id: 'a1', status: 'done', title: 'q', payload: { answer: 'A' } })
  await waitFor(() => expect(result.current).toHaveLength(1))
  expect(result.current[0].status).toBe('done')
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ui && npx vitest run src/__tests__/useArtifacts.test.tsx`
Expected: FAIL — current hook appends, so two `a1` entries exist (length 2).

- [ ] **Step 3: Update `ui/src/useArtifacts.ts`** to dedup by id (last write wins, order preserved):

```ts
import { useEffect, useState } from 'react'
import type { Artifact } from './types'
import { wsUrl } from './ws'

export function useArtifacts(sessionId: string, wsBase?: string): Artifact[] {
  const [artifacts, setArtifacts] = useState<Artifact[]>([])

  useEffect(() => {
    const ws = new WebSocket(wsUrl('/ws/artifacts', sessionId, wsBase))
    ws.onmessage = (ev: MessageEvent) => {
      const data = JSON.parse(ev.data) as Artifact
      setArtifacts((prev) => {
        const idx = prev.findIndex((a) => a.id === data.id)
        if (idx === -1) return [...prev, data]
        const next = [...prev]
        next[idx] = data
        return next
      })
    }
    return () => ws.close()
  }, [sessionId, wsBase])

  return artifacts
}
```

- [ ] **Step 4: Redesign `ui/src/App.tsx`** — add the audio bar, a live status line, and a cleaner structure. Replace the file with:

```tsx
import { useState } from 'react'
import { useTranscript } from './useTranscript'
import { useArtifacts } from './useArtifacts'
import { TranscriptPane } from './TranscriptPane'
import { ArtifactCard } from './ArtifactCard'
import { AskBox } from './AskBox'
import { AudioBar } from './AudioBar'
import { WikiPanel } from './WikiPanel'
import { postAsk } from './ask'
import { postUpload } from './upload'
import { postFinalize, getWiki } from './wiki'

const SESSION_ID =
  new URLSearchParams(window.location.search).get('session') ?? 'demo'

export default function App() {
  const events = useTranscript(SESSION_ID)
  const artifacts = useArtifacts(SESSION_ID)
  const [pending, setPending] = useState(false)

  async function handleAsk(query: string) {
    setPending(true)
    try {
      await postAsk(SESSION_ID, query)
    } finally {
      setPending(false)
    }
  }

  async function handleUpload(file: File) {
    await postUpload(SESSION_ID, file)
  }

  async function handleFinalize() {
    await postFinalize(SESSION_ID)
    return getWiki(SESSION_ID)
  }

  const live = events.length > 0

  return (
    <main className="app">
      <header className="app-header">
        <div className="brand">
          <span className="dot" data-live={live} />
          <h1>DeepTalk</h1>
        </div>
        <div className="header-right">
          <AudioBar onUpload={handleUpload} />
          <span className="session">session · {SESSION_ID}</span>
        </div>
      </header>

      <div className="panes">
        <section className="pane">
          <div className="pane-head">
            <h2 className="pane-title">Transcript</h2>
            <span className="count">{events.length}</span>
          </div>
          <TranscriptPane events={events} onLineClick={handleAsk} />
        </section>

        <section className="pane">
          <div className="pane-head">
            <h2 className="pane-title">Insights</h2>
            <span className="count">{artifacts.length}</span>
          </div>
          <AskBox onAsk={handleAsk} pending={pending} />
          <div className="cards">
            {artifacts.length === 0 && (
              <p className="cards-empty">
                Upload audio or ask a question — answers, pros/cons, plans and diagrams appear here live.
              </p>
            )}
            {[...artifacts].reverse().map((a) => (
              <ArtifactCard key={a.id} artifact={a} />
            ))}
          </div>
        </section>
      </div>

      <WikiPanel onFinalize={handleFinalize} />
    </main>
  )
}
```

- [ ] **Step 5: Restyle — append/replace in `ui/src/styles.css`** (intentional dark command-center; this REPLACES the `.app-header` block and ADDS the new classes — keep all existing card/transcript/wiki/ask styles):

Add these rules (and update `.app-header` to the new flex layout):
```css
.app { max-width: 72rem; }

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  border-bottom: 1px solid var(--line);
  padding-bottom: 1rem;
  margin-bottom: 1.5rem;
}

.brand { display: flex; align-items: center; gap: 0.6rem; }

.dot {
  width: 0.6rem; height: 0.6rem; border-radius: 50%;
  background: var(--muted);
}
.dot[data-live="true"] {
  background: oklch(72% 0.18 145);
  box-shadow: 0 0 0 0 oklch(72% 0.18 145 / 0.6);
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 oklch(72% 0.18 145 / 0.5); }
  70% { box-shadow: 0 0 0 0.5rem oklch(72% 0.18 145 / 0); }
  100% { box-shadow: 0 0 0 0 oklch(72% 0.18 145 / 0); }
}

.header-right { display: flex; align-items: center; gap: 1rem; }

.audiobar { display: flex; align-items: center; gap: 0.5rem; }
.audiobar-btn {
  background: var(--accent); color: var(--bg);
  border: none; border-radius: 0.5rem;
  padding: 0.45rem 0.9rem; font: inherit; font-weight: 600; cursor: pointer;
}
.audiobar-btn:disabled { opacity: 0.55; cursor: default; }
.audiobar-name { color: var(--muted); font-family: var(--mono); font-size: 0.8rem; max-width: 14rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.pane-head { display: flex; align-items: baseline; justify-content: space-between; }
.count {
  font-family: var(--mono); font-size: 0.7rem; color: var(--muted);
  background: var(--surface); border-radius: 1rem; padding: 0.05rem 0.5rem;
}

@media (prefers-reduced-motion: reduce) {
  .dot[data-live="true"] { animation: none; }
}
```
(Find the existing `.app-header { ... }` and `.app-header h1` rules and replace the `.app-header` block with the version above; keep `.app-header h1` and `.session`.)

- [ ] **Step 6: Typecheck, test, build**

Run:
```bash
cd ui && npm run typecheck && npm test && npm run build
```
Expected: typecheck clean; all UI tests pass (prior + upload 2 + AudioBar 2 + dedup 1); `dist/` built.

- [ ] **Step 7: End-to-end smoke (upload transcribes via fake → cards appear)**

```bash
cd .. && rm -f deeptalk-demo.db
uv run python -m deeptalk.server > /tmp/deeptalk-9a.log 2>&1 &
SERVER_PID=$!
sleep 4
# make a tiny 16k mono wav and upload it
uv run python -c "import wave,struct,math; w=wave.open('/tmp/clip.wav','wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b''.join(struct.pack('<h',0) for _ in range(1600))); w.close()"
echo "UPLOAD:"; curl -s -F "file=@/tmp/clip.wav;type=audio/wav" "http://127.0.0.1:8000/upload?session_id=demo"; echo
sleep 2
echo "TRANSCRIPT:"; uv run python -c "from deeptalk.transcript.store import TranscriptStore; print([e.text for e in TranscriptStore('deeptalk-demo.db').all_events('demo')][:3])"
kill $SERVER_PID 2>/dev/null
```
Expected: UPLOAD returns `{"events": N}` (N≥1, the fixture lines via fake STT); TRANSCRIPT prints the fixture lines. (On the GPU box with `DEEPTALK_STT=nemotron`, it transcribes the real audio instead.) Paste `/tmp/deeptalk-9a.log` tail on failure.

- [ ] **Step 8: Commit**

```bash
git add ui/src/useArtifacts.ts ui/src/App.tsx ui/src/styles.css ui/src/__tests__/useArtifacts.test.tsx
git commit -m "feat(ui): dedup artifacts by id; redesign dashboard with audio bar + live status"
```

---

## On the GPU box (real upload transcription)

```bash
uv sync --extra gpu
sudo apt-get install -y ffmpeg            # decode mp3/m4a
cd ui && npm install && npm run build && cd ..
DEEPTALK_STT=nemotron DEEPTALK_SEARCH_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-... \
  uv run python -m deeptalk.server
# open http://localhost:8000/ → "Upload audio" → pick an mp3 → real transcript + agent cards
```

---

## Self-Review

**Scope:** This phase adds the missing **in-browser audio input (file upload)** and a **dashboard redesign with live status**, addressing the two reported gaps. Browser live-mic streaming is Phase 9B (deliberately separate — needs WebSocket audio + AudioWorklet). Real transcription still depends on nemotron (GPU); fake STT keeps it demoable/testable on any machine.

**Placeholder scan:** No TBD/TODO. ffmpeg-dependent test is `skip`-guarded (not faked away). Every step has exact code + commands + expected output.

**Type consistency:** `decode_to_wav(src) -> str` (Task 1) used by `/upload` (Task 2). `build_stt(config, audio_source=None, realtime=True)` (Task 2) — lifespan's `build_stt(config)` still valid (defaults). `create_app(..., config=None)` consistent between Task 2 and the entrypoint (Task 2 step 5). `postUpload(sessionId, file, base?)` (Task 3) matches `/upload?session_id=` (Task 2) and `AudioBar.onUpload` / `App.handleUpload` (Tasks 3-4). `useArtifacts` dedup keeps the `Artifact[]` return type (Task 4) consumed unchanged by `App`/`ArtifactCard`.

**Known follow-ups:** real-time per-agent skeleton cards (needs backend pending artifacts) and browser live mic are 9B; `python-multipart` added for uploads.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-02-deeptalk-phase9a-upload-redesign.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review, continuous execution.

**2. Inline Execution** — executing-plans with checkpoints.

Which approach?
