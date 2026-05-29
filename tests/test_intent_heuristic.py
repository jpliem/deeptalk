from deeptalk.intent.heuristic import HeuristicIntentDetector
from deeptalk.intent.models import Intent, normalize_topic


async def test_detects_question_mark():
    d = HeuristicIntentDetector()
    intent = await d.detect("postgres or sqlite?")
    assert isinstance(intent, Intent)
    assert intent.kind == "search"
    assert intent.query == "postgres or sqlite?"


async def test_detects_leading_question_word():
    d = HeuristicIntentDetector()
    intent = await d.detect("should we use postgres or sqlite")
    assert intent is not None
    assert intent.kind == "search"


async def test_ignores_statement():
    d = HeuristicIntentDetector()
    assert await d.detect("postgres scales better for concurrent writes") is None


async def test_ignores_blank():
    d = HeuristicIntentDetector()
    assert await d.detect("   ") is None


def test_normalize_topic_collapses_case_and_punctuation():
    assert normalize_topic("Postgres or SQLite?") == normalize_topic("postgres  or sqlite")
