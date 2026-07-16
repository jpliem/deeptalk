from deeptalk.config import Config
from deeptalk.intent.factory import build_detector
from deeptalk.intent.heuristic import HeuristicIntentDetector
from deeptalk.intent.llm import LlmIntentDetector
from deeptalk.llm.factory import build_router


def test_factory_default_is_llm():
    cfg = Config.from_env({})
    d = build_detector(cfg, build_router(cfg))
    assert isinstance(d, LlmIntentDetector)


def test_factory_heuristic_when_selected():
    cfg = Config.from_env({"DEEPTALK_INTENT": "heuristic"})
    d = build_detector(cfg, build_router(cfg))
    assert isinstance(d, HeuristicIntentDetector)


def test_factory_llm_when_selected():
    cfg = Config.from_env({"DEEPTALK_INTENT": "llm"})
    d = build_detector(cfg, build_router(cfg))
    assert isinstance(d, LlmIntentDetector)
