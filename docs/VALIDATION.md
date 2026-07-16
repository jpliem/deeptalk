# GPU-Laptop Validation Checklist — STT hardening bundle

Everything below needs the real rig (Mac + GPU laptop). Unit tests already cover
the logic with fake PCM; this pass validates behavior on real speech.

## Setup

**GPU laptop** (192.168.110.115):

```bash
# The sidecar changed: it now accepts a `language` form field and caps
# max_new_tokens at 96. Restart it after pulling.
uv run python scratch/asr_sidecar.py
ollama serve   # if not already running
# Optional, for intent-model override validation:
ollama pull qwen2.5:7b
```

**Mac** — add to `.env` (values to tune during this session):

```bash
DEEPTALK_QWEN_LANGUAGE=en        # or zh — pick the meeting language
DEEPTALK_QWEN_RMS_THRESHOLD=200  # raise if noisy room, lower if soft speaker
DEEPTALK_INTENT_MODEL=qwen2.5:7b # optional: better classification
```

Run the server with log level INFO and watch for `deeptalk.orchestrator` lines —
fired intents, duplicate-topic skips, and garbled-line skips are all logged now.

## Checks

### 1. Language pinning
- [ ] Speak the meeting language for 2+ minutes, including short utterances and pauses.
- [ ] Confirm no transcript line comes out in the wrong language/script.
- [ ] Verify the `language` value is accepted by the qwen_asr package — if the
      sidecar errors on `model.transcribe(language=...)`, check what codes it
      expects (`en`/`zh` vs `English`/`Chinese`) and adjust `.env`.

### 2. Silence gate (RMS threshold tuning)
- [ ] Stay silent for 30 s with normal room noise: **no** transcript events and no
      sidecar requests (watch sidecar stdout) should appear.
- [ ] Speak softly from normal distance: speech **should** still be transcribed.
      If it is dropped, lower `DEEPTALK_QWEN_RMS_THRESHOLD` (try 120–150).
- [ ] Noisy room (fan/AC): if hallucinated text appears during non-speech, raise
      the threshold (try 300–400).

### 3. Phrase assembly / no mid-sentence agents
- [ ] Speak one long sentence slowly (5–8 s). It should arrive as **one** transcript
      bubble after you pause, not 3–4 fragments.
- [ ] Confirm no agent card fires until you finish the sentence.
- [ ] Speak continuously for 20+ s: a forced finalization should occur around 15 s
      (`DEEPTALK_QWEN_MAX_PHRASE_MS`).

### 4. Repeat suppression
- [ ] Watch for `the the the`-style loops in the transcript — should be collapsed.
- [ ] Trigger a stutter/um-heavy sentence; confirm text is reasonable.
- [ ] Grep server logs for `skipping garbled line` — those lines were blocked from
      firing agents. Confirm nothing legitimate is being blocked.

### 5. Intent quality (with DEEPTALK_INTENT_MODEL)
- [ ] Say a clear search question ("what is the pricing model of X") → search card.
- [ ] Say a debate line ("should we use postgres or sqlite") → pros/cons card.
- [ ] Say neutral chatter ("okay let's move on") → **no** card.
- [ ] Check logs for `intent detection failed` / `not parseable` warnings — these
      were previously silent failures.

### 6. Regression
- [ ] File upload (mp3) still transcribes.
- [ ] `/ask` manual question still answers with transcript context.
- [ ] Timeline still populates (Ollama reachable).
- [ ] `/finalize` builds the wiki.

## Tuning notes to record

| Setting | Tried | Result |
|---------|-------|--------|
| `DEEPTALK_QWEN_RMS_THRESHOLD` | | |
| `DEEPTALK_QWEN_LANGUAGE` value accepted | | |
| `DEEPTALK_QWEN_MAX_PHRASE_MS` | | |
| `DEEPTALK_INTENT_MODEL` | | |
