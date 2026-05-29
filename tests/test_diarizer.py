import importlib

from deeptalk.diarize.base import Diarizer
from deeptalk.diarize.fake import FakeDiarizer
from deeptalk.diarize.models import DiarizedSegment


async def test_fake_diarizer_returns_segments():
    segs = [DiarizedSegment(speaker=0, start=0.0, end=1.0, text="hello")]
    d = FakeDiarizer(segs)
    out = await d.diarize("/any/path.wav")
    assert out == segs


def test_fake_satisfies_protocol():
    assert isinstance(FakeDiarizer([]), Diarizer)


def test_vibevoice_module_imports_without_transformers():
    mod = importlib.import_module("deeptalk.diarize.vibevoice")
    assert hasattr(mod, "VibeVoiceDiarizer")


def test_vibevoice_exposes_diarize():
    from deeptalk.diarize.vibevoice import VibeVoiceDiarizer

    assert callable(getattr(VibeVoiceDiarizer, "diarize", None))
