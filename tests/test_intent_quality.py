from deeptalk.intent.models import Intent, normalize_topic
from deeptalk.intent.quality import looks_garbled
from deeptalk.orchestrator import Orchestrator


def test_garbled_empty_and_whitespace():
    assert looks_garbled("")
    assert looks_garbled("   ")


def test_garbled_token_loops():
    assert looks_garbled("the the the the the the")
    assert looks_garbled("thank you thank you thank you thank you thank you thank you")


def test_garbled_symbol_soup():
    assert looks_garbled("... --- ??? !!! ***")


def test_normal_speech_passes():
    assert not looks_garbled("should we use postgres or sqlite")
    assert not looks_garbled("yes")
    assert not looks_garbled("can you mockup the dashboard layout?")
    assert not looks_garbled("that's a very very good point")


class _StubDetector:
    def __init__(self):
        self.seen: list[str] = []

    async def detect(self, text: str) -> Intent | None:
        self.seen.append(text)
        return Intent(kind="search", query=text, topic=normalize_topic(text))


async def test_orchestrator_skips_garbled_lines_before_detection():
    detector = _StubDetector()
    fired: list[Intent] = []

    async def fire(intent: Intent) -> None:
        fired.append(intent)

    orch = Orchestrator(detector, fire)
    assert await orch.handle("the the the the the the") is None
    assert detector.seen == []
    assert fired == []

    intent = await orch.handle("what is the capital of France")
    assert intent is not None
    assert len(fired) == 1
