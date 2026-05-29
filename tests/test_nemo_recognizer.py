import importlib


def test_module_imports_without_nemo_or_torch():
    mod = importlib.import_module("deeptalk.stt.nemo_recognizer")
    assert hasattr(mod, "NemoCacheAwareRecognizer")


def test_class_exposes_transcribe_chunk():
    from deeptalk.stt.nemo_recognizer import NemoCacheAwareRecognizer

    assert callable(getattr(NemoCacheAwareRecognizer, "transcribe_chunk", None))
    assert callable(getattr(NemoCacheAwareRecognizer, "reset", None))
