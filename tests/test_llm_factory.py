from deeptalk.config import Config
from deeptalk.llm.factory import build_router


def test_ollama_intent_model_override_routes_intent_separately():
    cfg = Config.from_env(
        {
            "DEEPTALK_SEARCH_PROVIDER": "ollama",
            "DEEPTALK_OLLAMA_MODEL": "llama3.2:3b",
            "DEEPTALK_INTENT_MODEL": "qwen2.5:7b",
        }
    )
    router = build_router(cfg)

    intent_chain = router.chain_for("intent")
    search_chain = router.chain_for("search")
    assert [p._model for p in intent_chain] == ["qwen2.5:7b"]
    assert [p._model for p in search_chain] == ["llama3.2:3b"]


def test_ollama_without_intent_model_shares_one_chain():
    cfg = Config.from_env({"DEEPTALK_SEARCH_PROVIDER": "ollama"})
    router = build_router(cfg)
    assert router.chain_for("intent") == router.chain_for("search")


def test_intent_model_ignored_when_same_as_ollama_model():
    cfg = Config.from_env(
        {
            "DEEPTALK_SEARCH_PROVIDER": "ollama",
            "DEEPTALK_OLLAMA_MODEL": "llama3.2:3b",
            "DEEPTALK_INTENT_MODEL": "llama3.2:3b",
        }
    )
    router = build_router(cfg)
    assert router.chain_for("intent") == router.chain_for("search")
