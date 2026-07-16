from deeptalk.cost.tracker import CostTracker


async def test_allows_until_cap_then_denies():
    t = CostTracker(max_calls=2)
    assert await t.allow("s1") is True
    assert await t.allow("s1") is True
    assert await t.allow("s1") is False
    assert t.spent("s1") == 2


async def test_unlimited_when_negative():
    t = CostTracker(max_calls=-1)
    for _ in range(100):
        assert await t.allow("s1") is True


async def test_sessions_are_independent():
    t = CostTracker(max_calls=1)
    assert await t.allow("s1") is True
    assert await t.allow("s2") is True
    assert await t.allow("s1") is False
    assert await t.allow("s2") is False
