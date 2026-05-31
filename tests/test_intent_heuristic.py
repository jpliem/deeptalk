from deeptalk.intent.heuristic import HeuristicIntentDetector
from deeptalk.intent.models import Intent, normalize_topic


async def test_question_is_search():
    intent = await HeuristicIntentDetector().detect("what is rust")
    assert isinstance(intent, Intent) and intent.kind == "search"


async def test_question_mark_is_search():
    intent = await HeuristicIntentDetector().detect("is rust memory safe?")
    assert intent is not None and intent.kind == "search"


async def test_or_choice_is_debate():
    intent = await HeuristicIntentDetector().detect("should we use postgres or sqlite")
    assert intent is not None and intent.kind == "debate"


async def test_pros_and_cons_is_debate():
    intent = await HeuristicIntentDetector().detect("what are the pros and cons of kafka")
    assert intent is not None and intent.kind == "debate"


async def test_planning_phrase_is_planning():
    intent = await HeuristicIntentDetector().detect("how do we build the auth system")
    assert intent is not None and intent.kind == "planning"


async def test_lets_plan_is_planning():
    intent = await HeuristicIntentDetector().detect("let's plan the migration")
    assert intent is not None and intent.kind == "planning"


async def test_statement_is_none():
    assert await HeuristicIntentDetector().detect("postgres scales better for writes") is None


async def test_blank_is_none():
    assert await HeuristicIntentDetector().detect("   ") is None


def test_normalize_topic_stable():
    assert normalize_topic("Postgres or SQLite?") == normalize_topic("postgres  or sqlite")


async def test_mockup_signal_is_mockup():
    intent = await HeuristicIntentDetector().detect("can you mockup the dashboard")
    assert intent is not None and intent.kind == "mockup"


async def test_diagram_signal_is_mockup():
    intent = await HeuristicIntentDetector().detect("draw a diagram of the auth flow")
    assert intent is not None and intent.kind == "mockup"


async def test_wireframe_signal_is_mockup():
    intent = await HeuristicIntentDetector().detect("wireframe the login screen")
    assert intent is not None and intent.kind == "mockup"
