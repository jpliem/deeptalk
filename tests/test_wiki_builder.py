from deeptalk.wiki.builder import build_wiki
from deeptalk.wiki.models import Wiki
from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.router import ModelRouter


def _router(provider):
    return ModelRouter(providers={"p": provider}, routes={"wiki": ["p"]}, default=["p"])


async def test_build_wiki_from_completion():
    provider = FakeLlmProvider(
        completion='{"topics": ["db choice"], "decisions": ["use postgres"], "action_items": ["set up CI"]}'
    )
    wiki = await build_wiki(
        "s1", ["should we use postgres or sqlite"], ["search: postgres vs sqlite"], _router(provider), now=1.0
    )
    assert isinstance(wiki, Wiki)
    assert wiki.session_id == "s1"
    assert wiki.topics == ["db choice"]
    assert wiki.decisions == ["use postgres"]
    assert wiki.action_items == ["set up CI"]
    assert wiki.created_at == 1.0


async def test_build_wiki_empty_on_failure():
    class Boom:
        name = "boom"

        async def complete(self, prompt):
            raise RuntimeError("model down")

    wiki = await build_wiki("s1", ["hi"], [], _router(Boom()), now=0.0)
    assert wiki.topics == [] and wiki.decisions == [] and wiki.action_items == []


async def test_build_wiki_handles_empty_transcript():
    provider = FakeLlmProvider(completion='{"topics": [], "decisions": [], "action_items": []}')
    wiki = await build_wiki("s1", [], [], _router(provider), now=2.0)
    assert wiki.topics == []
