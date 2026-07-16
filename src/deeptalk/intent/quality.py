from __future__ import annotations

import re

_MIN_WORDS_FOR_REPETITION_CHECK = 6
_MAX_REPETITION_RATIO = 0.4  # unique/total below this reads as an ASR loop
_MIN_CHARS_FOR_SYMBOL_CHECK = 8
_MIN_WORD_CHAR_RATIO = 0.5  # mostly punctuation/symbols reads as noise


def looks_garbled(text: str) -> bool:
    """Heuristic gate for ASR output too tangled to act on.

    Catches the two dominant live-STT failure shapes — hallucinated token
    loops ("the the the the ...") and symbol soup from overlapped/noisy
    audio — so the intent detector never fires agents on them. Normal short
    utterances pass through untouched.
    """
    line = text.strip()
    if not line:
        return True

    words = line.lower().split()
    if len(words) >= _MIN_WORDS_FOR_REPETITION_CHECK:
        if len(set(words)) / len(words) < _MAX_REPETITION_RATIO:
            return True

    compact = re.sub(r"\s+", "", line)
    if len(compact) >= _MIN_CHARS_FOR_SYMBOL_CHECK:
        word_chars = len(re.findall(r"\w", compact))
        if word_chars / len(compact) < _MIN_WORD_CHAR_RATIO:
            return True

    return False
