from __future__ import annotations

import subprocess
import tempfile
import wave


def _ffmpeg_cmd(src: str, dst: str, rate: int = 16000) -> list[str]:
    return [
        "ffmpeg", "-y", "-i", src,
        "-ac", "1",
        "-ar", str(rate),
        "-sample_fmt", "s16",
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
